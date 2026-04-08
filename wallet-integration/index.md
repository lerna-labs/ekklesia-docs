---
layout: default
title: Wallet Integration
description:
  How to integrate CIP-8 message signing authentication with Ekklesia.
---

This guide covers how to authenticate users and submit votes programmatically
using Cardano wallet signing. If you're building your own frontend or
integration tool, this is the place to start.

## Authentication Flow

Ekklesia uses a **challenge-response** authentication model with **CIP-8 message
signing**:

### 1. Request a Nonce

```
POST /api/v0/session
Body: { signerAddress, signType }
```

Provide the signer's address and sign type to receive a challenge nonce.

### 2. Sign the Challenge

Sign the returned nonce using CIP-8 message signing. This works with both
browser wallets (via CIP-30's `signData`) and CLI tools like CardanoSigner.

```javascript
// Example using CIP-30 browser wallet
const api = await window.cardano[walletName].enable();
const signature = await api.signData(address, nonceHex);
```

### 3. Verify and Receive JWT

```
PUT /api/v0/session
Body: { signerAddress, signType, signature }
```

On success, a JWT session cookie is set. Include it in subsequent authenticated
requests.

## Signature Formats

Ekklesia supports two signature formats:

- **Ed25519** — Raw key signature (CardanoSigner, CLI tools)
- **COSE (CIP-8)** — Standard message signing format from browser wallets

## MultiSig Support

Ekklesia supports voting with MultiSig wallets. The system validates signatures
against native scripts to verify that the signer is an authorized key within the
MultiSig configuration.

Key considerations for MultiSig integration:

- When casting votes, **all required signatures must be present** and satisfy
  the terms of the native script
- The system fetches and parses the native script to validate that the script's
  conditions are fully met
- Both `sig` (single key) and `all`/`any`/`atLeast` script types are supported

## Voter Types

Ballots can restrict eligibility to specific voter groups:

| Voter Type           | Identifier                                 |
| -------------------- | ------------------------------------------ |
| **DRep**             | DRep credential (CIP-105/CIP-129)          |
| **SPO**              | Pool ID, cold key or Calidus key (CIP-151) |
| **Address**          | Bech32 address or stake credential         |
| **Token/NFT holder** | Policy ID + asset verification             |

The specific voter types for a ballot are defined in the ballot configuration.
Query the ballot details endpoint to see which groups are eligible.
