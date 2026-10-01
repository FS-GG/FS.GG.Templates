# Rust and Go hosted BIND qualification evidence

This record closes the hosted BIND gate for the Rust Tic-tac-toe and Go Snake rows of V2-LANG-01.5.
It does not close publication, installed adoption, another route or the parent matrix.

## Protected execution

- Workflow run: `36815503862`, successful.
- Protected Templates source: `eb914297fdd9b6b7d7e85a18a2ee0e341451b421`.
- Source tree: `fb15b4c244c09459da272e04a962a02d309c4458`.
- Qualification schema: `fsgg.language-route.hosted-qualification/1`; `accepted: true`.
- `qualification.json` SHA-256: `afed1c27d46d3df9a7e8c4426038e5a4a328220157e561e2cb6bc87c5db0c8be`.
- Validator record SHA-256: `a6ffc2796d8f993532ca7b5fe6f2211a192cb7baadf67659bc413ce280663c07`;
  its `evidenceSha256` equals the qualification SHA-256.

The workflow consumed public source artifact `11112465308` from run `36744671457` and bound its downloaded
ZIP to SHA-256 `d3ede2552d45357e505de41f34603adb458a815a20fc43dedae13f1650a56027`.
It built Coordination source `c069263c3e9e8780b1596eee82d2f6c017daa8df` under SDK `10.0.400` and
matched executor SHA-256 `6395cdf3feb6ee114685920d9ba8b48b624df01bb1d38b922b12da0bffa89daf`
and Akka 1.5.71 SHA-256 `1ef266d80a923b25db758987a15e4db99acaa05863a236871bac4dbd6315c5b7`.

GitHub retained the workflow output as artifact `11141456884`, size `888304032` bytes. Artifact metadata
reported ZIP SHA-256 `20de1e0d212146c57cfb900528e44fad9c21340e822690487bc5eb609d37076d`.
The independent readback used 69 bounded HTTP range requests to retrieve 22 selected JSON members totaling
41,590 bytes. It did not download or independently hash the complete output ZIP.

## Fresh-loaded image identities

| Route | Retained reference and manifest | Config digest | Load receipt SHA-256 |
|---|---|---|---|
| Rust | `localhost/fsgg-language-route-rust:retained-20260930@sha256:41f2a51451a6213d3f504fa5164b2ed16d7281b8de861546360cdc7d983f3c23` | `sha256:e72ef546069bf2478e35fbdf60f374e263caf852e08ba62a96868b80191fc2e8` | `866dae8987cc9e4020a0dda4aee491d5d786352b4f07bd5f44baa74453a548e1` |
| Go | `localhost/fsgg-language-route-go:retained-20260930@sha256:5f2aa99db0d6e06badb69391c4c863a8662e4d9c609db2c28517ef637a91518b` | `sha256:7a1cfd29f845b19c55c75645ecfb3ed0edd0d812f2323a7a0151e779d2d0e269` | `a4722aaa92fd52c00da38d57a28940a8830b3360e49c73b19b4393d1c869ecf5` |

Both loads used fresh isolated VFS stores. The inspected bare storage IDs canonicalized to the exact config
digests above; neither identity substitutes for the retained manifest selector.

## Journey and settlement receipts

| Route | Command identity | Container identity | First / duplicate / recovered receipt SHA-256 |
|---|---|---|---|
| Rust | `b41ea42a-7160-4274-aa67-540016f63a4b`; `8d18276ad3618dc7a9be765f2dfe493c992318a14c927b87a941fc4a7270ca74` | `cd9c6f851b3a3928340f2f2c257f00382cdd75df2565372fe22f63ee555fec62` | `12609107b0c26057059cb6e31448960838d428d83cdc2bff2e49f76ee37bd0f2` / `096bb6d95f2c785e7a0191b6acf855458cd5a5f6e88792c895b0d32856328f68` / `66e99634bfa824bfab5b26d1e5cb10544bc7b65081daaf11f02fe9c8aa1937f1` |
| Go | `f9c058b5-ad7b-41aa-b593-a9e13c5b275c`; `e368fa66632395075bd4b6f5d080b0b6f5ac858569a9378ac41cbc1e706494d9` | `65e7bbf8ccf8329b279fce6a6c5be6789d792cbc7eaaf512f0a48cd4fbc0ce10` | `f1ca806268eaf58a8ed550b05cf136f24fffc826a10ac90aee1f8c47d16afdae` / `9361c6702637b460a11fe29da68a422bef765cee3a49e0a09456fc408ac15022` / `dee646c9770d6a4aa55c3ed2c1e147e088bce0c0ac6e89f543746d4cbd18d982` |

Each first receipt is `completed`; each same-process duplicate and fresh-process recovery is `duplicate`.
Within each row all three receipts retain the same command ID, command SHA-256, source revision/tree, image,
container identity, snapshot, runtime identity, output hash and successful verification output hash.

The separate Rust cancellation command is `b2634cae-a2b4-4f51-b191-ecbad44e8749`, command SHA-256
`0e24cc281fc938ba28c4988406c09ebc0641226cfce25907a915e0b3aa13ca86`, and container identity
`783fa82ca776a669fe7f5460f86e1cdfd99a3757064b890661eb6e18a52c76cb`. Its first receipt SHA-256 is
`de183900ffd141bf79a2c8df87f64fa5d2ecfcbb717e55c5e13891c091b83444`; it records an observed running
operation, `execution-cancelled`, execution start, cancellation request, termination, cleanup and bounded
cleanup recovery. Fresh-process recovery returned the same settled identity as a duplicate; that receipt's
SHA-256 is `1d61966279fddfbb56631a2d35ba63e943da4905fb7de3979f618021417fd012`.

## Refusal and cleanup closure

The same executor refused all three negative probes before launch:

- changed source: `portable-executor-source-binding-refused`;
- wrong retained image reference: `portable-executor-image-binding-refused`;
- wrong toolchain: `portable-executor-toolchain-refused`.

Cleanup evidence SHA-256 `39f9e59b5183517ff90224f869bc1316410b259bcc730136e872f68772401c99`
records `containersAbsent: true` and removal of the owned `preflight`, `rust` and `go` namespaces.

## Remaining dependency

Rust and Go next require the coherent P3 producer publication and P4 installed receiver window. Installed
creation and retained upgrade evidence must select the published bytes without adding a product SDK dependency.
Python Hello, TypeScript Todo, FourD and the composed TypeScript/Python route retain their own BIND and ADOPT
gates. V2-LANG-01.5 remains open until all six declared routes meet the plan's CLOSE gate.
