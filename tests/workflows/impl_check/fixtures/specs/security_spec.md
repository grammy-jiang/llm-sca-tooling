# Security Specification

## Secrets Management

The application must never log plaintext passwords or secrets.
The `encrypt` function must use AES-256 or stronger encryption.
The system shall validate all user inputs to prevent injection attacks.
