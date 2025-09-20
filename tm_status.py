import time
import subprocess
import re
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.text import Text

console = Console()

import subprocess
import re

def parse_tmutil_status(output):
    """Parses the tmutil status output including nested Progress dictionary."""
    data = {}
    progress_block = False
    progress_data = {}

    for line in output.strip().splitlines():
        line = line.strip()

        # Start of nested "Progress = {"
        if line.startswith("Progress = {"):
            progress_block = True
            continue

        # End of nested block
        if progress_block and line == "};":
            progress_block = False
            data.update(progress_data)
            continue

        # Inside nested block
        if progress_block:
            if '=' in line:
                key, value = map(str.strip, line.strip(';').split('=', 1))
                progress_data[key] = value.strip('"')
        else:
            if '=' in line:
                key, value = map(str.strip, line.strip(';').split('=', 1))
                data[key] = value.strip('"')

    return data

def get_tmutil_status():
    """Fetches and parses the tmutil status output."""
    try:
        result = subprocess.run(['tmutil', 'status'], capture_output=True, text=True, check=True)
        return parse_tmutil_status(result.stdout)
    except subprocess.CalledProcessError as e:
        return {"Error": f"Command failed: {e.stderr.strip()}"}
    except FileNotFoundError:
        return {"Error": "tmutil command not found. Are you on macOS?"}

def format_bytes(bytes_str):
    """Converts a byte string to a human-readable format."""
    try:
        bytes_val = int(float(bytes_str))
        units = ["B", "KB", "MB", "GB", "TB", "PB", "EB"]
        index = 0
        while bytes_val >= 1024 and index < len(units) - 1:
            bytes_val /= 1024
            index += 1
        return f"{bytes_val:.2f} {units[index]}"
    except (ValueError, TypeError):
        return bytes_str  

def format_time_duration(seconds_str):
    """Converts seconds to hh:mm:ss format."""
    try:
        total_seconds = int(float(seconds_str))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    except (ValueError, TypeError):
        return seconds_str

def get_formatted_table():
    """Creates a Rich Table with formatted tmutil status."""
    status_data = get_tmutil_status()
    
    table = Table(title="[bold green]Time Machine Backup Status[/bold green]", style="bold green", show_header=True, header_style="bold magenta")

    table.add_column("Parameter", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    # Mapping keys to display names and formatting functions
    display_map = {
        "BackupPhase": {"label": "Backup Phase", "formatter": lambda x: f"[b blue]{x}[/b blue]"},
        "ChangedItemCount": {"label": "Changed Items"},
        "ClientID": {"label": "Client ID"},
        "DateOfStateChange": {"label": "Last State Change"},
        "DestinationID": {"label": "Destination ID", "visible": False}, 
        "DestinationMountPoint": {"label": "Destination Mount"},
        "FractionDone": {"label": "Progress", "formatter": lambda x: f"{float(x)*100:.2f}%" if x.replace('.', '', 1).isdigit() else x},
        "FractionOfProgressBar": {"label": "Progress Bar Fraction", "visible": False}, 
        "Running": {"label": "Running", "formatter": lambda x: "[green]Yes[/green]" if x == "1" else "[red]No[/red]"},
        "BytesCopied": {"label": "Bytes Copied", "formatter": format_bytes},
        "TotalBytesToCopy": {"label": "Total Bytes to Copy", "formatter": format_bytes},
        "TimeRemaining": {"label": "Time Remaining", "formatter": format_time_duration},
        "Error": {"label": "Error", "formatter": lambda x: f"[bold red]{x}[/bold red]"},
        "Percent": {
            "label": "Progress",
            "formatter": lambda x: f"{float(x) * 100:.2f}%" if x.replace('.', '', 1).isdigit() else x
        },
        "_raw_Percent": {
            "label": "_raw_Percent",
            "visible": False
        }


    }

    # Automatically add new keys with formatting
    for key, value in status_data.items():
        if key not in display_map:
            if "bytes" in key.lower():
                display_map[key] = {"label": key, "formatter": format_bytes}
            elif "time remaining" in key.lower():
                display_map[key] = {"label": key, "formatter": format_time_duration}
            else:
                display_map[key] = {"label": key}

    # Add relevant rows to the table
    for key, info in display_map.items():
        if not info.get("visible", True):
            continue

        value = status_data.get(key, "N/A")
        formatter = info.get("formatter", lambda x: x) # Default formatter is identity
        
        # Special handling for FractionDone to combine with a progress bar-like text
        if key in ("FractionDone", "Percent") and value != "N/A" and value.replace('.', '', 1).isdigit():
            fraction = float(value)
            percent_text = f"{fraction * 100:.2f}%"
            progress_bar_length = 20
            filled_length = int(progress_bar_length * fraction)
            bar = "[green]█[/green]" * filled_length + "[grey]░[/grey]" * (progress_bar_length - filled_length)
            
            table.add_row(info["label"], percent_text)
            table.add_row("Progress Bar", bar)
        else:
            table.add_row(info["label"], formatter(value))

    return table

if __name__ == "__main__":
    console.print("[bold yellow]Monitoring Time Machine status... Press Ctrl+C to exit.[/bold yellow]\n")
    
    # Use Rich's Live context manager for automatic refresh and clearing
    with Live(get_formatted_table(), refresh_per_second=1, screen=True) as live:
        try:
            while True:
                live.update(get_formatted_table())
                time.sleep(1) # Sleep is still needed to control the update interval
        except KeyboardInterrupt:
            console.print("\n[bold blue]Monitoring stopped.[/bold blue]")
