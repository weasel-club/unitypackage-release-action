# unitypackage-release-action

Build one or more `.unitypackage` artifacts from declarative JSON package definitions.

## Inputs

- `version` (required): output filename version suffix
- `output_dir` (optional, default: `output`)
- `packages_json` (required): JSON array of package definitions

## Package definition schema

```json
[
  {
    "package_name": "SeeThroughHair",
    "include_roots": ["Assets", "Editor", "Runtime", "SeeThroughHair.asmdef"],
    "target_root": "Assets/SeeThroughHair",
    "script_allowlist_file": ".github/fakeshadow-scripts.txt",
    "exclude_paths": ["Assets/Legacy"],
    "missing_meta_policy": "error",
    "skip_hidden": true
  }
]
```

Fields:
- `package_name` (string, required)
- `include_roots` (string[], required)
- `target_root` (string, required)
- `script_allowlist_file` (string, optional)
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
    version: ${{ github.ref_name }}
    output_dir: output
    packages_json: |
      [
        {
          "package_name": "MMDEyeFix",
          "include_roots": ["Editor", "Runtime", "package.json"],
          "target_root": "Assets/MMDEyeFix"
        }
      ]
```
