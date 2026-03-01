#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import shutil

VALID_MISSING_META_POLICY = {"error", "skip"}


@dataclass(frozen=True)
class PackageConfig:
    package_name: str
    output_file_name: str
    include_roots: list[Path]
    allowlist: list[str] | None
    target_root: Path
    exclude_paths: set[Path]
    missing_meta_policy: str
    skip_hidden: bool


class ConfigError(RuntimeError):
    pass


def read_guid(meta_path: Path) -> str:
    for line in meta_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("guid: "):
            return line.split("guid: ", 1)[1].strip()
    raise ConfigError(f"guid not found in {meta_path.as_posix()}")


def add_virtual_folder(target_path: Path, work_dir: Path) -> None:
    guid = hashlib.md5(target_path.as_posix().encode("utf-8")).hexdigest()
    guid_dir = work_dir / guid
    guid_dir.mkdir(parents=True, exist_ok=True)

    folder_meta = (
        "fileFormatVersion: 2\n"
        f"guid: {guid}\n"
        "folderAsset: yes\n"
        "DefaultImporter:\n"
        "  externalObjects: {}\n"
        "  userData: \n"
        "  assetBundleName: \n"
        "  assetBundleVariant: \n"
    )
    (guid_dir / "asset.meta").write_text(folder_meta, encoding="utf-8")
    (guid_dir / "pathname").write_text(target_path.as_posix(), encoding="utf-8")


def add_asset(asset_path: Path, target_path: Path, work_dir: Path, missing_meta_policy: str) -> None:
    meta_path = asset_path.parent / f"{asset_path.name}.meta"
    if not meta_path.exists():
        if missing_meta_policy == "skip":
            return
        raise ConfigError(f"missing meta file: {meta_path.as_posix()}")

    guid = read_guid(meta_path)
    guid_dir = work_dir / guid
    guid_dir.mkdir(parents=True, exist_ok=True)

    if asset_path.is_file():
        shutil.copy2(asset_path, guid_dir / "asset")

    shutil.copy2(meta_path, guid_dir / "asset.meta")
    (guid_dir / "pathname").write_text(target_path.as_posix(), encoding="utf-8")


def is_hidden(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def is_excluded(path: Path, excludes: set[Path]) -> bool:
    for excluded in excludes:
        if path == excluded or excluded in path.parents:
            return True
    return False


def normalize_glob(pattern: str) -> str:
    if pattern.startswith("./"):
        return pattern[2:]
    return pattern


def matches_allowlist(rel_path: Path, allowlist: list[str] | None) -> bool:
    if allowlist is None:
        return True

    rel_posix = rel_path.as_posix()
    pure_rel = PurePosixPath(rel_posix)
    for raw_pattern in allowlist:
        pattern = normalize_glob(raw_pattern)
        if pure_rel.match(pattern):
            return True
        if fnmatch.fnmatch(rel_posix, pattern):
            return True
    return False


def collect_included_files(project_root: Path, config: PackageConfig) -> list[Path]:
    included: set[Path] = set()

    for include_root in config.include_roots:
        source = project_root / include_root
        if not source.exists():
            continue

        rel_source = source.relative_to(project_root)
        if config.skip_hidden and is_hidden(rel_source):
            continue
        if is_excluded(rel_source, config.exclude_paths):
            continue

        if source.is_file():
            if source.suffix == ".meta":
                continue
            if not matches_allowlist(rel_source, config.allowlist):
                continue
            included.add(rel_source)
            continue

        for file_path in sorted(source.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix == ".meta":
                continue

            rel_file = file_path.relative_to(project_root)
            if config.skip_hidden and is_hidden(rel_file):
                continue
            if is_excluded(rel_file, config.exclude_paths):
                continue
            if not matches_allowlist(rel_file, config.allowlist):
                continue

            included.add(rel_file)

    return sorted(included, key=lambda p: p.as_posix())


def collect_required_directories(included_files: list[Path]) -> list[Path]:
    directories: set[Path] = set()
    for rel_file in included_files:
        parent = rel_file.parent
        while parent != Path("."):
            directories.add(parent)
            parent = parent.parent
    return sorted(directories, key=lambda p: (len(p.parts), p.as_posix()))


def build_single_package(project_root: Path, output_dir: Path, config: PackageConfig) -> Path:
    included_files = collect_included_files(project_root, config)
    if not included_files:
        raise ConfigError(f"no files selected for package '{config.package_name}'")

    included_dirs = collect_required_directories(included_files)

    work_dir = output_dir / f"unitypackage-{config.package_name}"
    shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    add_virtual_folder(config.target_root, work_dir)

    for rel_dir in included_dirs:
        add_asset(
            project_root / rel_dir,
            config.target_root / rel_dir,
            work_dir,
            config.missing_meta_policy,
        )

    for rel_file in included_files:
        add_asset(
            project_root / rel_file,
            config.target_root / rel_file,
            work_dir,
            config.missing_meta_policy,
        )

    package_path = output_dir / config.output_file_name
    if package_path.exists():
        package_path.unlink()

    with tarfile.open(package_path, "w:gz", compresslevel=1) as tar:
        for entry in sorted(work_dir.iterdir()):
            tar.add(entry, arcname=entry.name)

    return package_path


def parse_package_config(raw: dict) -> PackageConfig:
    required_fields = ("package_name", "output_file_name", "include_roots", "target_root")
    for field in required_fields:
        if field not in raw:
            raise ConfigError(f"missing required field '{field}' in package definition")

    package_name = raw["package_name"]
    output_file_name = raw["output_file_name"]
    include_roots_raw = raw["include_roots"]
    target_root = raw["target_root"]

    if not isinstance(package_name, str) or not package_name:
        raise ConfigError("package_name must be a non-empty string")
    if not isinstance(output_file_name, str) or not output_file_name:
        raise ConfigError("output_file_name must be a non-empty string")
    if "/" in output_file_name or "\\" in output_file_name:
        raise ConfigError("output_file_name must be a filename, not a path")
    if not output_file_name.endswith(".unitypackage"):
        raise ConfigError("output_file_name must end with .unitypackage")
    if not isinstance(include_roots_raw, list) or not include_roots_raw:
        raise ConfigError("include_roots must be a non-empty string array")
    if not isinstance(target_root, str) or not target_root:
        raise ConfigError("target_root must be a non-empty string")

    include_roots: list[Path] = []
    for entry in include_roots_raw:
        if not isinstance(entry, str) or not entry:
            raise ConfigError("include_roots must contain only non-empty strings")
        include_roots.append(Path(entry))

    allowlist: list[str] | None = None
    if "allowlist" in raw and raw["allowlist"] is not None:
        allowlist_raw = raw["allowlist"]
        if not isinstance(allowlist_raw, list) or not allowlist_raw:
            raise ConfigError("allowlist must be a non-empty string array when provided")

        parsed_allowlist: list[str] = []
        for entry in allowlist_raw:
            if not isinstance(entry, str) or not entry:
                raise ConfigError("allowlist must contain only non-empty strings")
            parsed_allowlist.append(entry)
        allowlist = parsed_allowlist

    exclude_paths: set[Path] = set()
    if "exclude_paths" in raw:
        if not isinstance(raw["exclude_paths"], list):
            raise ConfigError("exclude_paths must be a string array")
        for entry in raw["exclude_paths"]:
            if not isinstance(entry, str) or not entry:
                raise ConfigError("exclude_paths must contain only non-empty strings")
            exclude_paths.add(Path(entry))

    missing_meta_policy = raw.get("missing_meta_policy", "error")
    if missing_meta_policy not in VALID_MISSING_META_POLICY:
        raise ConfigError("missing_meta_policy must be one of: error, skip")

    skip_hidden = raw.get("skip_hidden", True)
    if not isinstance(skip_hidden, bool):
        raise ConfigError("skip_hidden must be boolean")

    return PackageConfig(
        package_name=package_name,
        output_file_name=output_file_name,
        include_roots=include_roots,
        allowlist=allowlist,
        target_root=Path(target_root),
        exclude_paths=exclude_paths,
        missing_meta_policy=missing_meta_policy,
        skip_hidden=skip_hidden,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Unitypackage artifacts from JSON package definitions")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--packages-json", required=True)
    parser.add_argument("--github-output", required=False)
    return parser.parse_args()


def write_outputs(github_output: Path | None, generated_files: list[Path], output_dir: Path) -> None:
    if github_output is None:
        return

    lines = [path.relative_to(output_dir).as_posix() for path in generated_files]
    if lines:
        content = "generated_files<<EOF\n" + "\n".join(lines) + "\nEOF\n"
    else:
        content = "generated_files=\n"
    with github_output.open("a", encoding="utf-8") as f:
        f.write(content)


def main() -> int:
    args = parse_args()

    project_root = Path(".").resolve()
    output_dir = (project_root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        raw_packages = json.loads(args.packages_json)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"packages_json is not valid JSON: {exc}") from exc

    if not isinstance(raw_packages, list) or not raw_packages:
        raise ConfigError("packages_json must be a non-empty JSON array")

    package_configs: list[PackageConfig] = []
    for raw in raw_packages:
        if not isinstance(raw, dict):
            raise ConfigError("each package definition must be a JSON object")
        package_configs.append(parse_package_config(raw))

    generated_files: list[Path] = []
    for config in package_configs:
        generated = build_single_package(project_root, output_dir, config)
        generated_files.append(generated)

    github_output = Path(args.github_output) if args.github_output else None
    write_outputs(github_output, generated_files, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
