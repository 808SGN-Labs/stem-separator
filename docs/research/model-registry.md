# Model Registry Specification

The registry should present producer-friendly information while retaining technical provenance.

Example:

```yaml
id: melband-kj
display_name: MelBand KJ

model:
  architecture: melband-roformer
  task: vocals
  checkpoint: vocals_mel_band_roformer.ckpt
  checkpoint_hash: TBD

capabilities:
  cpu: true
  offline_when_installed: true

benchmark:
  reference_system: TBD
  rtf: TBD
  peak_ram: TBD
  quality_metrics: TBD

provenance:
  creator: Kimberley Jensen
  source: TBD
  license: TBD
  redistribution: TBD
```

Unknown license or redistribution status must remain `TBD`/unknown until verified.

Producer labels such as FAST, BALANCED or QUALITY must be derived from benchmark evidence rather than assigned arbitrarily.
