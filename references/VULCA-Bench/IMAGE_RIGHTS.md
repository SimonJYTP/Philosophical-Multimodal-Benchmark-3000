# Image Rights Boundary

VULCA-Bench v2.1 is a **metadata-only public repository**. It does not redistribute artwork image files.

The row-level record is `data/license_rights_manifest_v2_1.csv`. For all 7,236 release rows:

- `can_redistribute_image=false`
- `license_label=source_specific_not_relicensed`
- `metadata_license=CC BY 4.0`
- `critique_license=CC BY 4.0`

The release manifest further records:

| Rights state | Rows |
| --- | ---: |
| Source-side retrieval required | 7,136 |
| Embedded review only | 100 |
| Image redistribution permitted by this release | 0 |
| Rows with a public `source_url` | 0 |
| Rows with a public `image_url` | 0 |

A local `image_path` is a provenance reference only. It does not establish copyright ownership, identify a public download location, or grant permission to copy, publish, train on, or redistribute an image.

Anyone retrieving an image must independently identify the authoritative source, review its current terms and rights statement, preserve required attribution, and document the legal basis for the intended use. If that basis cannot be established, do not retrieve or use the image.

The Hugging Face dataset is a separate existing distribution surface. Its current embedded-image state is under reconciliation and is not changed by this repository release candidate.
