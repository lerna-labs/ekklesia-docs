---
layout: default
title: Supported Wallets
description: Wallet requirements for voting on Ekklesia.
---

Ekklesia's wallet requirements depend on the voter type for a given ballot.

## Requirements by Voter Type

| Voter Type                    | Required Standard   | Notes                           |
| ----------------------------- | ------------------- | ------------------------------- |
| **Address/Token/NFT holders** | CIP-30 + CIP-8      | Message signing via payment key |
| **DReps**                     | CIP-95              | Governance key signing          |
| **SPOs**                      | CIP-151 or cold key | Calidus key or cold key signing |

Any Cardano wallet that implements the required CIP standard should be
compatible. We have not yet exhaustively tested all wallets — if you encounter
issues with a specific wallet, please let us know.

## Hardware Wallets

Hardware wallets (e.g., Ledger, Keystone) should work when connected through a
compatible browser extension that supports the required CIP standard.

## CLI / MultiSig

You can authenticate and vote using
**[CardanoSigner](https://github.com/gitmachtl/cardano-signer)**. Most MultiSig
configurations are supported — see the [Wallet Integration
guide]({{ '/wallet-integration/' | relative_url }}) for technical details.
