# Midtrans Payment Automation (Testing Only)

This repository contains a Python script for **automated testing** of Midtrans payment flows using the official **Sandbox** environment.

**Important Note:** This project does **not** support reverse-engineering the Midtrans Snap frontend or automating payments in the Production environment. Such actions violate security best practices and Terms of Service. This tool is intended solely for developers to verify their integrations in a safe, sandboxed environment.

## Prerequisites

- Python 3.x
- Midtrans Server Key and Client Key (Sandbox)

## Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

## Usage

Set your Sandbox keys as environment variables:

```bash
export MIDTRANS_SERVER_KEY="your-server-key"
export MIDTRANS_CLIENT_KEY="your-client-key"
```

Run the script:

```bash
python midtrans_integration.py
```
