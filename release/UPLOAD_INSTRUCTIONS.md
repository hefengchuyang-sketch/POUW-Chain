# Offline Upload Instructions

## Option A: Use Git bundle (recommended)

1. Copy `maincoin-main-f9287f9.bundle` to a machine with GitHub network access.
2. Run:

```bash
git clone maincoin-main-f9287f9.bundle maincoin-offline
cd maincoin-offline
git remote add origin https://github.com/hefengchuyang-sketch/POUW-Chain.git
git push origin main
```

## Option B: Apply patch files on top of origin/main

1. Clone repo normally on a machine with network access:

```bash
git clone https://github.com/hefengchuyang-sketch/POUW-Chain.git
cd POUW-Chain
```

2. Copy patch files and apply:

```bash
git am 0001-refactor-rpc-migrate-method-registration-to-domain-h.patch
git am 0002-feat-consensus-introduce-sbox_primary-mode-with-pouw.patch
```

3. Push:

```bash
git push origin main
```

## Included commits

- d6eea69 refactor(rpc): migrate method registration to domain handlers and harden test gating
- f9287f9 feat(consensus): introduce sbox_primary mode with pouw support ratio
