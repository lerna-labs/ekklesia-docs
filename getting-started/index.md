---
layout: default
title: Getting Started
description: How to connect your wallet and vote on Ekklesia.
---

## Connecting Your Wallet

The wallet requirements depend on your voter type:

- **Address/Token/NFT holders** — Any **CIP-30** compatible wallet that supports
  **CIP-8** message signing
- **DReps** — A wallet that supports **CIP-95** message signing specifically
- **SPOs** — Cold key or **Calidus key (CIP-151)** signing

Connect your wallet using the button in the top-right corner of any Ekklesia
voting instance.

Any Cardano wallet that supports the required CIP standard for your voter type
should work. See [Supported Wallets]({{ '/wallets/' | relative_url }}) for more
details on requirements.

You can also authenticate via CLI using
[CardanoSigner](https://github.com/gitmachtl/cardano-signer), which supports
MultiSig configurations.

## How Voting Works

1. **Connect** your wallet to the Ekklesia instance
2. **Browse** live ballots you are eligible to vote on
3. **Select** your choices and save your vote
4. **Sign and submit** — your vote must be signed with your wallet to be counted

<div class="callout callout-warning">
<strong>Important:</strong> All votes must be signed and submitted. If you see a red "Pending Votes" alert, you still need to sign and submit for your votes to be included in the results.
</div>

You can change your vote as often as you want while a ballot is live.

## Checking Results

- Results are rolled up every **10 minutes** while a ballot is live
- You can look up any voter's activity in the **Voter Directory**
- Final results are published on-chain after a ballot closes and can be
  independently verified

## Eligibility

Eligible voter groups may vary from ballot to ballot. If you are logged in but
cannot vote, make sure you are connected with a wallet that belongs to an
eligible voter group for that particular ballot.
