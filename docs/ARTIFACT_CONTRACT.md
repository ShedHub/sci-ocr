# Artifact Contract

This pipeline has three stages:

- `layout`
- `ocr`
- `assembly`

JSON artifacts pass between stages. Each stage reads the previous stage's JSON
output and writes its own JSON output for the next stage.
