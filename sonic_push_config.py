#!/usr/bin/env python3
"""
Dell SONiC Switch Configuration Script

This script applies a text configuration file to a Dell SONiC switch.
The hostname is extracted from the configuration file name.

Usage:
    python sonic_push_config.py <config_file> [options]

Example:
    python sonic_push_config.py switch01.txt --username admin --password admin123
"""

import argparse
import os
import sys
import re
import time
import getpass
import socket
from pathlib import Path
import paramiko
from paramiko import SSHClient, AutoAddPolicy
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sonic_push_config.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def resolve_hostname(hostname, hosts_file='hosts.txt'):
    """
    Resolve hostname to IP address using hosts.txt file first, then system resolver
    
    Args:
        hostname (str): The hostname to resolve
        hosts_file (str): Path to the hosts file (default: 'hosts.txt')
    
    Returns:
        str: IP address if resolved, original hostname if resolution fails
    """
    # First try to resolve using hosts.txt file
    if os.path.exists(hosts_file):
        try:
            with open(hosts_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse line format: IP_ADDRESS HOSTNAME [ALIAS1] [ALIAS2] ...
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    
                    ip_address = parts[0]
                    hostnames = parts[1:]  # All remaining parts are hostnames/aliases
                    
                    # Check if our hostname matches any of the hostnames/aliases
                    if hostname.lower() in [h.lower() for h in hostnames]:
                        logger.info(f"Resolved {hostname} to {ip_address} via hosts.txt")
                        return ip_address
                        
        except Exception as e:
            logger.warning(f"Error reading hosts file '{hosts_file}': {e}")
    else:
        logger.debug(f"Hosts file '{hosts_file}' not found, will use system resolver")
    
    # If not found in hosts.txt, try system resolver
    try:
        ip_address = socket.gethostbyname(hostname)
        if ip_address != hostname:  # If resolution was successful
            logger.info(f"Resolved {hostname} to {ip_address} via system resolver")
            return ip_address
    except socket.gaierror as e:
        logger.warning(f"Could not resolve hostname '{hostname}' via system resolver: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error resolving hostname '{hostname}': {e}")
    
    # If all resolution methods fail, return original hostname
    logger.warning(f"Using original hostname '{hostname}' as IP resolution failed")
    return hostname

def validate_hosts_file(hosts_file='hosts.txt'):
    """
    Validate the hosts.txt file format and log any issues
    
    Args:
        hosts_file (str): Path to the hosts file
    
    Returns:
        bool: True if file is valid or doesn't exist, False if format issues found
    """
    if not os.path.exists(hosts_file):
        logger.info(f"Hosts file '{hosts_file}' not found - system resolver will be used")
        return True
    
    valid = True
    
    try:
        with open(hosts_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split()
                if len(parts) < 2:
                    logger.warning(f"hosts.txt line {line_num}: Invalid format - need at least IP and hostname")
                    valid = False
                    continue
                
                ip_address = parts[0]
                
                # Basic IP address validation
                try:
                    socket.inet_aton(ip_address)  # Check if valid IPv4
                except socket.error:
                    try:
                        socket.inet_pton(socket.AF_INET6, ip_address)  # Check if valid IPv6
                    except socket.error:
                        logger.warning(f"hosts.txt line {line_num}: Invalid IP address '{ip_address}'")
                        valid = False
                        continue
                
                hostnames = parts[1:]
                logger.debug(f"hosts.txt entry: {ip_address} -> {', '.join(hostnames)}")
    
    except Exception as e:
        logger.error(f"Error validating hosts file '{hosts_file}': {e}")
        return False
    
    if valid:
        logger.info(f"Hosts file '{hosts_file}' validated successfully")
    else:
        logger.warning(f"Hosts file '{hosts_file}' has format issues but will continue")
    
    return valid

def extract_hostname_from_filename(filename):
    """Extract hostname from configuration filename - specifically looking for sw + up to 8 digits"""
    # Remove file extension and path
    basename = Path(filename).stem
    
    # Pattern to match "sw" followed by up to 8 digits
    sw_pattern = r'((.)sw\d{1,8})'
    
    # Search for the sw pattern (case-insensitive)
    match = re.search(sw_pattern, basename, re.IGNORECASE)
    
    if match:
        hostname = match.group(1).lower()  # Convert to lowercase for consistency
        logger.info(f"Found SW switch name: {hostname}")
        return hostname
    
    # If no sw pattern found, log warning and return basename
    logger.warning(f"No SW switch name pattern found in filename '{filename}'")
    logger.warning("Expected pattern: sw + up to 8 digits (e.g., esw123, esw12345678)")
    return basename

class SONiCConfigApplier:
    """Class to handle SONiC switch configuration application"""
    
    def __init__(self, hostname, username, password, port=22, timeout=30, hosts_file='hosts.txt'):
        self.hostname = hostname
        # Resolve hostname to IP address
        self.ip_address = resolve_hostname(hostname, hosts_file)
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self.ssh_client = None
        
    def connect(self):
        """Establish SSH connection to the switch"""
        try:
            self.ssh_client = SSHClient()
            self.ssh_client.set_missing_host_key_policy(AutoAddPolicy())
            
            logger.info(f"Connecting to {self.hostname} ({self.ip_address}):{self.port}")
            self.ssh_client.connect(
                hostname=self.ip_address,  # Use resolved IP address
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
                look_for_keys=False,
                allow_agent=False
            )
            logger.info("Successfully connected to switch")
            return True
            
        except paramiko.AuthenticationException:
            logger.error("Authentication failed")
            return False
        except paramiko.SSHException as e:
            logger.error(f"SSH connection error: {e}")
            return False
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False
    
    def disconnect(self):
        """Close SSH connection"""
        if self.ssh_client:
            self.ssh_client.close()
            logger.info("Disconnected from switch")
    
    def execute_command(self, command, wait_time=1):
        """Execute a single command on the switch"""
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            
            # Wait for command to complete
            exit_status = stdout.channel.recv_exit_status()
            
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            if exit_status != 0 and error:
                logger.warning(f"Command '{command}' returned error: {error}")
            
            time.sleep(wait_time)  # Brief pause between commands
            return output, error, exit_status
            
        except Exception as e:
            logger.error(f"Error executing command '{command}': {e}")
            return None, str(e), -1
    
    def execute_sonic_cli_session(self, commands):
        """Execute commands in a SONiC CLI session using an interactive shell"""
        try:
            # Create an interactive shell session
            shell = self.ssh_client.invoke_shell()
            shell.settimeout(10)
            
            # Wait for initial prompt
            time.sleep(1)
            output = shell.recv(1024).decode('utf-8')
            logger.debug(f"Initial prompt: {output}")
            
            # Start sonic-cli
            logger.info("Starting SONiC CLI session")
            shell.send('sonic-cli\n')
            time.sleep(2)
            
            # Read the sonic-cli startup output
            startup_output = shell.recv(4096).decode('utf-8')
            logger.debug(f"SONiC CLI startup: {startup_output}")
            
            # Enter configuration mode
            logger.info("Entering configuration mode")
            shell.send('configure\n')
            time.sleep(1)
            
            # Read configure command output
            config_output = shell.recv(1024).decode('utf-8')
            logger.debug(f"Configure output: {config_output}")
            
            # Execute configuration commands
            failed_commands = []
            for i, command in enumerate(commands, 1):
                logger.info(f"[{i}/{len(commands)}] Executing: {command}")
                
                # Send command
                shell.send(f'{command}\n')
                time.sleep(0.5)  # Brief pause between commands
                
                # Read response
                try:
                    response = shell.recv(2048).decode('utf-8')
                    logger.debug(f"Response: {response}")
                    
                    # Check for error indicators in response
                    if 'Error' in response or 'error' in response or 'Invalid' in response:
                        failed_commands.append((command, response.strip()))
                        logger.error(f"Command failed: {command}")
                        logger.error(f"Error response: {response.strip()}")
                    
                except Exception as e:
                    logger.warning(f"Could not read response for command '{command}': {e}")
            
            # Exit configuration mode
            logger.info("Exiting configuration mode")
            shell.send('end\n')
            time.sleep(1)
            
            # Save configuration
            logger.info("Saving configuration to memory")
            shell.send('write memory\n')
            time.sleep(2)
            
            # Read final responses
            try:
                final_output = shell.recv(4096).decode('utf-8')
                logger.debug(f"Final output: {final_output}")
                
                # Check if write memory was successful
                if 'Error' in final_output or 'error' in final_output:
                    failed_commands.append(("write memory", final_output.strip()))
                    logger.error("Failed to save configuration")
                else:
                    logger.info("Configuration saved successfully")
                    
            except Exception as e:
                logger.warning(f"Could not read final output: {e}")
            
            # Exit sonic-cli
            shell.send('exit\n')
            time.sleep(1)
            
            # Close the shell
            shell.close()
            
            return len(failed_commands) == 0, failed_commands
            
        except Exception as e:
            logger.error(f"Error in SONiC CLI session: {e}")
            return False, [("session_error", str(e))]
    
    def execute_sonic_cli_single_command(self, commands):
        """Execute all commands in a single SONiC CLI session using heredoc or piping"""
        try:
            # Create a single command that pipes all commands to sonic-cli
            command_list = ['configure'] + commands + ['end', 'write memory', 'exit']
            
            # Create a command string that pipes all commands to sonic-cli
            full_command = 'echo -e "' + '\\n'.join(command_list) + '" | sonic-cli'
            
            logger.info(f"Executing SONiC CLI with {len(commands)} configuration commands")
            logger.debug(f"Full command: {full_command}")
            
            stdin, stdout, stderr = self.ssh_client.exec_command(full_command)
            
            # Wait for command to complete
            exit_status = stdout.channel.recv_exit_status()
            
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            logger.debug(f"SONiC CLI output: {output}")
            if error:
                logger.debug(f"SONiC CLI stderr: {error}")
            
            # Parse output for errors
            failed_commands = []
            output_lines = output.split('\n')
            
            for line in output_lines:
                if 'Error' in line or 'error' in line or 'Invalid' in line:
                    # Try to match the error to a command
                    failed_commands.append(("unknown_command", line.strip()))
                    logger.error(f"Error in output: {line.strip()}")
            
            if exit_status != 0:
                logger.error(f"SONiC CLI session failed with exit status: {exit_status}")
                if error:
                    failed_commands.append(("session_error", error))
            
            return len(failed_commands) == 0, failed_commands
            
        except Exception as e:
            logger.error(f"Error executing SONiC CLI single command: {e}")
            return False, [("execution_error", str(e))]

    def enter_config_mode(self):
        """Enter SONiC configuration mode - deprecated, now handled in execute_sonic_cli_session"""
        logger.warning("enter_config_mode() is deprecated - configuration mode is now handled in execute_sonic_cli_session()")
        return True
    
    def exit_config_mode(self):
        """Exit SONiC configuration mode - deprecated, now handled in execute_sonic_cli_session"""
        logger.warning("exit_config_mode() is deprecated - configuration mode exit is now handled in execute_sonic_cli_session()")
        return True

    def apply_config_file(self, config_file_path):
        """Apply configuration from file using SONiC CLI session"""
        try:
            with open(config_file_path, 'r') as f:
                config_lines = f.readlines()
            
            logger.info(f"Reading configuration from {config_file_path}")
            logger.info(f"Found {len(config_lines)} configuration lines")
            
            # Filter out empty lines and comments
            config_commands = []
            for line in config_lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('!'):
                    config_commands.append(line)
            
            logger.info(f"Applying {len(config_commands)} configuration commands")
            
            # Try interactive session first, fall back to single command method
            logger.info("Attempting to use interactive SONiC CLI session")
            success, failed_commands = self.execute_sonic_cli_session(config_commands)
            
            if not success and failed_commands:
                # Check if it's a session error, try alternative method
                session_errors = [cmd for cmd, error in failed_commands if cmd in ["session_error", "execution_error"]]
                if session_errors:
                    logger.warning("Interactive session failed, trying single command method")
                    success, failed_commands = self.execute_sonic_cli_single_command(config_commands)
            
            return success, failed_commands
            
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {config_file_path}")
            return False, []
        except Exception as e:
            logger.error(f"Error applying configuration: {e}")
            return False, []
    
    def backup_current_config(self, backup_path):
        """Backup current configuration"""
        try:
            logger.info("Creating configuration backup")
            output, error, status = self.execute_command("show running-configuration")
            
            if status == 0 and output:
                with open(backup_path, 'w') as f:
                    f.write(output)
                logger.info(f"Configuration backed up to {backup_path}")
                return True
            else:
                logger.error(f"Failed to backup configuration: {error}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return False

def get_config_files(config_path):
    """Get list of configuration files from a single file or directory"""
    config_files = []
    
    if os.path.isfile(config_path):
        # Single file
        config_files.append(config_path)
        logger.info(f"Single configuration file: {config_path}")
    elif os.path.isdir(config_path):
        # Directory - get all files with common config extensions
        config_extensions = ['.txt', '.conf', '.cfg', '.config']
        
        for file in os.listdir(config_path):
            file_path = os.path.join(config_path, file)
            if os.path.isfile(file_path):
                # Check if file has a config extension or no extension
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in config_extensions or file_ext == '':
                    config_files.append(file_path)
        
        config_files.sort()  # Sort files alphabetically
        logger.info(f"Found {len(config_files)} configuration files in directory: {config_path}")
        
        if not config_files:
            logger.warning(f"No configuration files found in directory: {config_path}")
            logger.warning("Looking for files with extensions: .txt, .conf, .cfg, .config, or no extension")
    else:
        logger.error(f"Path does not exist: {config_path}")
        return []
    
    return config_files

def process_multiple_switches(config_files):
    """Process multiple configuration files and group by switch hostname"""
    switch_configs = {}
    
    for config_file in config_files:
        hostname = extract_hostname_from_filename(config_file)
        if hostname not in switch_configs:
            switch_configs[hostname] = []
        switch_configs[hostname].append(config_file)
    
    return switch_configs

def main():
    parser = argparse.ArgumentParser(
        description='Apply configuration file to Dell SONiC switch',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python sonic_push_config.py esw123.txt
  python sonic_push_config.py configs/
  python sonic_push_config.py /path/to/configs/ --hostname esw456
  python sonic_push_config.py switch_configs/ --backup
  python sonic_push_config.py esw123.txt --hosts-file /path/to/custom_hosts.txt
        '''
    )
    
    parser.add_argument('config_path', help='Path to configuration file or directory containing configuration files')
    parser.add_argument('--username', '-u', help='SSH username (will prompt if not provided)')
    parser.add_argument('--prompt-password', action='store_true', default=True,
                       help='Prompt for password (secure input, supports all special characters)')
    parser.add_argument('--hostname', help='Switch hostname/IP (if not extracted from filename)')
    parser.add_argument('--port', type=int, default=22, help='SSH port (default: 22)')
    parser.add_argument('--timeout', type=int, default=30, help='SSH timeout (default: 30)')
    parser.add_argument('--backup', action='store_true', 
                       help='Create backup of current configuration')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without applying changes')
    parser.add_argument('--hosts-file', default='hosts.txt',
                       help='Path to hosts file for hostname resolution (default: hosts.txt)')
    parser.add_argument('--validate-hosts', action='store_true',
                       help='Validate hosts file format and exit')
    
    args = parser.parse_args()
    
    # Validate hosts file if requested
    if args.validate_hosts:
        logger.info(f"Validating hosts file: {args.hosts_file}")
        if validate_hosts_file(args.hosts_file):
            logger.info("Hosts file validation passed")
            sys.exit(0)
        else:
            logger.error("Hosts file validation failed")
            sys.exit(1)
    
    # Validate hosts file format
    validate_hosts_file(args.hosts_file)
    
    # Validate config path exists
    if not os.path.exists(args.config_path):
        logger.error(f"Configuration path not found: {args.config_path}")
        sys.exit(1)
    
    # Get list of configuration files
    config_files = get_config_files(args.config_path)
    if not config_files:
        logger.error("No configuration files found")
        sys.exit(1)
    
    # Group configuration files by switch hostname
    switch_configs = process_multiple_switches(config_files)
    
    logger.info(f"Found configuration files for {len(switch_configs)} switches:")
    for hostname, files in switch_configs.items():
        # Show resolved IP for each hostname
        resolved_ip = resolve_hostname(hostname, args.hosts_file)
        ip_info = f" -> {resolved_ip}" if resolved_ip != hostname else ""
        logger.info(f"  {hostname}{ip_info}: {len(files)} file(s)")
        for file in files:
            logger.info(f"    - {file}")
    
    # Get username
    if args.username:
        username = args.username
    else:
        username = input("Enter SSH username: ")
    
    # Get password via secure prompt
    password = getpass.getpass("Enter SSH password: ")
    
    # Determine target switches
    if args.hostname:
        # Single switch specified
        if args.hostname not in switch_configs:
            logger.error(f"No configuration files found for hostname: {args.hostname}")
            sys.exit(1)
        target_switches = {args.hostname: switch_configs[args.hostname]}
    else:
        # Use all switches found
        target_switches = switch_configs
    
    # Dry run - show configuration without applying
    if args.dry_run:
        logger.info("DRY RUN MODE - Configuration will not be applied")
        logger.info(f"Target switches: {list(target_switches.keys())}")
        
        total_commands = 0
        for hostname, target_files in target_switches.items():
            resolved_ip = resolve_hostname(hostname, args.hosts_file)
            ip_info = f" ({resolved_ip})" if resolved_ip != hostname else ""
            logger.info(f"\nSwitch: {hostname}{ip_info}")
            logger.info(f"Configuration files: {len(target_files)}")
            
            switch_commands = []
            for config_file in target_files:
                logger.info(f"Configuration file: {config_file}")
                try:
                    with open(config_file, 'r') as f:
                        lines = f.readlines()
                    
                    config_commands = [line.strip() for line in lines 
                                     if line.strip() and not line.startswith('#') and not line.startswith('!')]
                    
                    logger.info(f"  Commands from {config_file} ({len(config_commands)}):")
                    for i, cmd in enumerate(config_commands, 1):
                        print(f"    {i:3d}: {cmd}")
                    
                    switch_commands.extend(config_commands)
                    
                except Exception as e:
                    logger.error(f"Error reading config file {config_file}: {e}")
            
            logger.info(f"Total commands for {hostname}: {len(switch_commands)}")
            total_commands += len(switch_commands)
        
        logger.info(f"\nGrand total commands to be applied: {total_commands}")
        sys.exit(0)
    
    # Process each switch
    overall_success = True
    switch_results = {}
    
    for hostname, target_files in target_switches.items():
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing switch: {hostname}")
        logger.info(f"Configuration files: {len(target_files)}")
        logger.info(f"{'='*60}")
        
        # Create configuration applier for this switch
        applier = SONiCConfigApplier(hostname, username, password, args.port, args.timeout, args.hosts_file)
        
        try:
            # Connect to switch
            if not applier.connect():
                logger.error(f"Failed to connect to switch {hostname}")
                switch_results[hostname] = {"success": False, "error": "Connection failed"}
                overall_success = False
                continue
            
            # Create backup if requested
            if args.backup:
                backup_filename = f"{hostname}_backup_{int(time.time())}.conf"
                if not applier.backup_current_config(backup_filename):
                    logger.warning(f"Failed to create backup for {hostname}, continuing anyway...")
            
            # Apply configuration files for this switch
            logger.info(f"Applying configuration from {len(target_files)} file(s) to {hostname}")
            
            switch_success = True
            all_failed_commands = []
            
            for i, config_file in enumerate(target_files, 1):
                logger.info(f"Processing file {i}/{len(target_files)}: {config_file}")
                success, failed_commands = applier.apply_config_file(config_file)
                
                if not success:
                    switch_success = False
                    all_failed_commands.extend(failed_commands)
                    logger.error(f"Configuration file {config_file} completed with errors")
                else:
                    logger.info(f"Configuration file {config_file} applied successfully")
            
            if switch_success:
                logger.info(f"All configuration files applied successfully to {hostname}!")
                switch_results[hostname] = {"success": True, "files_processed": len(target_files)}
            else:
                logger.error(f"Configuration for {hostname} completed with {len(all_failed_commands)} errors:")
                for cmd, error in all_failed_commands:
                    logger.error(f"  {cmd}: {error}")
                switch_results[hostname] = {
                    "success": False, 
                    "error": f"{len(all_failed_commands)} command failures",
                    "failed_commands": all_failed_commands
                }
                overall_success = False
                
        except KeyboardInterrupt:
            logger.info("Operation cancelled by user")
            switch_results[hostname] = {"success": False, "error": "Cancelled by user"}
            overall_success = False
            break
        except Exception as e:
            logger.error(f"Unexpected error processing {hostname}: {e}")
            switch_results[hostname] = {"success": False, "error": str(e)}
            overall_success = False
        finally:
            applier.disconnect()
    
    # Print summary
    logger.info(f"\n{'='*60}")
    logger.info("CONFIGURATION SUMMARY")
    logger.info(f"{'='*60}")
    
    successful_switches = []
    failed_switches = []
    
    for hostname, result in switch_results.items():
        if result["success"]:
            successful_switches.append(hostname)
            files_count = result.get("files_processed", 0)
            logger.info(f"✓ {hostname}: SUCCESS ({files_count} files processed)")
        else:
            failed_switches.append(hostname)
            error = result.get("error", "Unknown error")
            logger.error(f"✗ {hostname}: FAILED - {error}")
    
    logger.info(f"\nSuccessful: {len(successful_switches)}/{len(target_switches)}")
    logger.info(f"Failed: {len(failed_switches)}/{len(target_switches)}")
    
    if not overall_success:
        logger.error("Some switches failed configuration. Check logs above for details.")
        sys.exit(1)
    else:
        logger.info("All switches configured successfully!")

if __name__ == "__main__":
    main()