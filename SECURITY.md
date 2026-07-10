# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ |

## Security Considerations

### Extended Attributes

FileTag stores tags as extended attributes (xattr) on the filesystem. This is a standard POSIX feature and does not introduce any security vulnerabilities by itself. However:

- **Metadata visibility**: Extended attributes are visible to any user with read access to the file. Do not store sensitive information in tags.
- **Attribute limits**: Some filesystems have limits on xattr size (typically 4KB-64KB). FileTag keeps tags compact, but very large numbers of tags could hit these limits.
- **Filesystem compatibility**: Not all filesystems support xattr. FileTag provides clear error messages when xattr is not supported.

### Input Validation

- All tag names are validated against a strict regex (`^[a-zA-Z0-9_.-]+$`) to prevent injection attacks
- Tag names are limited to 64 characters
- File paths are resolved via `Path.resolve()` to prevent path traversal
- Paths are verified to exist before operations

### No Network Access

FileTag is entirely offline. It does not make any network calls, phone home, or send data anywhere.

### Permissions

FileTag respects filesystem permissions. You can only read/write tags on files you have access to.

## Reporting a Vulnerability

If you find a security vulnerability, please open an issue at:
https://github.com/EdgarOrtegaRamirez/filetag/issues

Do not email — just open a public issue.