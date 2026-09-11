# T053 audit questions

These are questions for human review, not automatic corrections or adjudicated facts.

## Questions

- **q-2a — case case-474f458c08d3bd7a9bf8**: Is the 2A relation intended to be agonist-bound A, and what relation kind should it represent? Source text: 'agonist-bound A(2A) adenosine receptor (AR)' [413, 456).
- **q-hdl-apoai — case case-8deab3bbe026a86e6b5c**: Are the HDL2-apoA-I and HDL4-apoA-I occurrences supported definitions that were not recorded as current decisions? Source text: 'HDL2-apoA-I' [565, 576), 'HDL4-apoA-I' [698, 709).
- **q-tcpo — case case-06c9ebb850190d98a90b**: Should shared material and trailing ‘tensions’ be treated as evidence for tcPO2/tcPCO2, or as separate components? Source text: 'Transcutaneous oxygen (tcPO2) and carbon dioxide (tcPCO2) tensions' [374, 440).
- **q-ratios — case case-1a4f2e3443392fdca836**: Should ratio components be represented separately from the whole ratio definitions? Source text: 'LDL-PL/LDL-apoB' [693, 708), 'VLDL3-C, VLDL4-C' [1173, 1189).
- **q-hdl1-typo — case case-8deab3bbe026a86e6b5c**: Is the repeated HDL1-PL text a source typo for HDL2-PL, and how should the source error be recorded? Source text: 'subclasses 1 (HDL1-PL) and 2 (HDL1-PL)' [254, 292).
- **q-vldl-mapping — case case-1a4f2e3443392fdca836**: Is VLDL3-C/VLDL4-C one long-form occurrence mapping to two short forms, or two separate definitions? Source text: 'VLDL3-C, VLDL4-C' [1173, 1189).
- **q-d-group — case case-bb7cec40d4228dda23e5**: Should D-group and the component mnemonics be represented as abbreviations, labels, or another relation kind? Source text: 'D-group' [156, 163), '(C-group)' [394, 403), '(H-group)' [438, 447).

The full reviewed passages and all current decisions are in `audit-packet.json` and `inventory.json`.

Reproduction:

```powershell
.\env313\Scripts\python.exe scripts\build_t053_audit_inventory.py
```
