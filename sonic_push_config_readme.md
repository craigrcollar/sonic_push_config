# SONiC Switch Configuration Script

A Python script for applying configuration files to Dell SONiC switches via SSH. This tool automatically extracts switch hostnames from configuration filenames and supports both single switch and bulk configuration operations.

## Features

- **Automatic hostname extraction** from configuration filenames using pattern matching
- **Bulk configuration support** for multiple switches from a directory
- **Interactive SONiC CLI session** with fallback to single command method
- **Configuration backup** before applying changes
- **Dry-run mode** to preview changes without applying them
- **Comprehensive logging** to both file and console
- **Error handling** with detailed reporting of failed commands
- **Secure password input** using getpass for enhanced security

## Requirements

### Python Version
- Python 3.6 or higher

### Dependencies
```bash
pip install paramiko
```

### System Requirements
- SSH access to target SONiC switches
- Network connectivity to switches
- Valid credentials with configuration privileges

## Installation

1. Clone or download the script:
```bash
wget https://your-repo/sonic_push_config.py
# or
curl -O https://your-repo/sonic_push_config.py
```

2. Install required dependencies:
```bash
pip install paramiko
```

3. Make the script executable (optional):
```bash
chmod +x sonic_push_config.py
```

## Usage

### Basic Syntax
```bash
python sonic_push_config.py <config_path> [options]
```

### Single Switch Configuration
```bash
# Apply configuration to a single switch
python sonic_push_config.py esw123.txt

# Specify custom hostname
python sonic_push_config.py switch_config.txt --hostname 192.168.1.10

# Create backup before applying
python sonic_push_config.py esw123.txt --backup
```

### Bulk Configuration
```bash
# Apply all configuration files in a directory
python sonic_push_config.py /path/to/configs/

# Target specific switch from directory
python sonic_push_config.py configs/ --hostname esw456
```

### Dry Run Mode
```bash
# Preview changes without applying
python sonic_push_config.py configs/ --dry-run
```

## Configuration File Naming Convention

The script automatically extracts switch hostnames from configuration filenames using the following pattern:

**Pattern**: `sw` followed by 1-8 digits (case-insensitive)

### Valid Examples:
- `esw123.txt` → hostname: `esw123`
- `ESW12345678.conf` → hostname: `esw12345678`
- `sw1.cfg` → hostname: `sw1`
- `backup_esw456_config.txt` → hostname: `esw456`

### Supported File Extensions:
- `.txt`
- `.conf`
- `.cfg`
- `.config`
- No extension

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `config_path` | Path to configuration file or directory | Required |
| `--username`, `-u` | SSH username | Prompt if not provided |
| `--prompt-password` | Prompt for password securely | `True` |
| `--hostname` | Override hostname extraction | Auto-extract from filename |
| `--port` | SSH port | `22` |
| `--timeout` | SSH connection timeout (seconds) | `30` |
| `--backup` | Create configuration backup | `False` |
| `--dry-run` | Preview changes without applying | `False` |

## Configuration File Format

Configuration files should contain SONiC CLI commands, one per line:

```
# This is a comment
interface Ethernet0
 description "Uplink Port"
 no shutdown
!
interface Ethernet1
 description "Server Connection"
 switchport mode access
 switchport access vlan 100
```

### Supported Elements:
- **Commands**: Standard SONiC CLI configuration commands
- **Comments**: Lines starting with `#` or `!`
- **Empty lines**: Ignored during processing

## Examples

### Example 1: Single Switch with Backup
```bash
python sonic_push_config.py esw123.txt --backup --username admin
```

### Example 2: Bulk Configuration with Dry Run
```bash
python sonic_push_config.py /opt/switch-configs/ --dry-run
```

### Example 3: Custom Hostname and Port
```bash
python sonic_push_config.py custom_config.txt --hostname 10.0.0.1 --port 2222
```

## Logging

The script provides comprehensive logging to both console and file:

- **Log file**: `sonic_push_config.log` (created in current directory)
- **Log levels**: INFO, WARNING, ERROR, DEBUG
- **Timestamps**: All log entries include timestamps
- **Command tracking**: Individual command execution status

### Log File Contents:
- Connection attempts and status
- Configuration commands executed
- Error messages and failed commands
- Backup creation status
- Summary of operations

## Error Handling

The script includes robust error handling for common scenarios:

### Connection Errors:
- Authentication failures
- Network connectivity issues
- SSH connection timeouts
- Invalid hostnames or ports

### Configuration Errors:
- Invalid SONiC CLI commands
- Syntax errors in configuration files
- Permission denied for configuration changes
- File system errors

### Recovery Strategies:
- Automatic fallback from interactive to single command mode
- Detailed error reporting for troubleshooting
- Graceful handling of partial failures
- Connection cleanup on interruption

## Security Considerations

- **Password Security**: Uses `getpass` for secure password input
- **SSH Key Management**: Automatically accepts new host keys (configurable)
- **Credential Handling**: Passwords are not logged or displayed
- **Connection Security**: Uses SSH for encrypted communication

## Troubleshooting

### Common Issues:

1. **Connection Refused**
   - Verify SSH is enabled on the switch
   - Check network connectivity
   - Confirm port number (default: 22)

2. **Authentication Failed**
   - Verify username and password
   - Check account permissions
   - Ensure account is not locked

3. **Configuration Commands Fail**
   - Review SONiC CLI command syntax
   - Check configuration mode requirements
   - Verify user has configuration privileges

4. **Hostname Not Extracted**
   - Ensure filename follows naming convention
   - Use `--hostname` option to specify manually
   - Check filename pattern: `sw` + 1-8 digits

### Debug Mode:
Modify the logging level in the script for more verbose output:
```python
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Code Style:
- Follow PEP 8 guidelines
- Add docstrings for new functions
- Include error handling
- Update documentation for new features

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, questions, or contributions:
- Create an issue in the repository
- Contact the development team
- Review existing documentation and logs

## Changelog

### Version 1.0.0
- Initial release
- Basic configuration application
- Hostname extraction from filenames
- Bulk configuration support
- Backup functionality
- Dry-run mode
- Comprehensive logging