# unitypackage-release-action

Build one or more `.unitypackage` artifacts from declarative JSON package definitions.

## Inputs

- `output_dir` (optional, default: `output`)
- `packages_json` (required): JSON array of package definitions

## Package definition schema

```json
[
  {
    "package_name": "SeeThroughHair",
    "output_file_name": "SeeThroughHair-1.2.3.unitypackage",
    "include_roots": ["Assets", "Editor", "Runtime", "SeeThroughHair.asmdef"],
    "allowlist": ["Assets/**/*", "Editor/**/*", "Runtime/**/*", "SeeThroughHair.asmdef"],
    "target_root": "Assets/SeeThroughHair",
    "exclude_paths": ["Assets/Legacy"],
    "missing_meta_policy": "error",
    "skip_hidden": true
  }
]
```

Fields:
- `package_name` (string, required)
- `output_file_name` (string, required, must end with `.unitypackage`)
- `include_roots` (string[], required)
- `allowlist` (string[], optional, glob patterns relative to repository root)
- `target_root` (string, required)
- `exclude_paths` (string[], optional)
- `missing_meta_policy` (`error` or `skip`, optional, default `error`)
- `skip_hidden` (boolean, optional, default `true`)

## Outputs

- `generated_files`: newline-separated list of generated `.unitypackage` relative file paths.

## Example

```yaml
- name: Build unitypackage
  uses: weasel-club/unitypackage-release-action@v1
  with:
    output_dir: output
    packages_json: |
      [
        {
          "package_name": "MMDEyeFix",
          "output_file_name": "MMDEyeFix-${{ github.ref_name }}.unitypackage",
          "include_roots": ["Editor", "Runtime", "package.json"],
          "allowlist": ["Editor/**/*", "Runtime/**/*", "package.json"],
          "target_root": "Assets/MMDEyeFix"
        }
      ]
```
