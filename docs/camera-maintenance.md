# Camera bundle maintenance

The public installer under `scripts/features/` embeds its runner and compressed
bundle. Its source data and pinned upstream patches live in
`maintainer/camera-port/`. Keep the embedded runner consistent with `installer.py`.

Generate in a scratch directory, using explicit paths:

```bash
python3 maintainer/camera-port/prepare_bundle.py \
  --root /path/to/rom --donor /path/to/vendor_oneplus_aston \
  --staging /path/to/new-scratch-directory
python3 maintainer/camera-port/export_bundle.py \
  --root /path/to/rom --donor /path/to/vendor_oneplus_aston \
  --staging /path/to/new-scratch-directory \
  --output /path/to/candidate/apply-aston-camera.sh
```

Use a new or empty staging directory. The donor is the pinned camera vendor
checkout described in the manifests. The generator reads the checkout and
creates scratch before/after files; it does not apply changes to live ROM source.
The exporter writes the candidate script, resolved patch and bundle summary
beside the selected output. Review them before replacing release files.

`finish_bundle.py` and `prepare_private_camera.py` are fragments executed by the
preparation process, not standalone commands. Run the camera regression checks
and the publication audit after any regeneration. Preserve upstream notices,
asset checksums and the previous-bundle compatibility inputs.
