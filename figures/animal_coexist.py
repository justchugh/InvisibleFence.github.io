#!/usr/bin/env python3
import argparse
import subprocess
import sys
import time
import signal
import os
import logging
import fcntl
from pathlib import Path
import tempfile
import atexit
import datetime

#####################################################################
# CONFIGURATION SECTION - Edit these values to customize operation
#####################################################################
# System settings
MAIN_SCRIPT = "main.py"         # Name of the main application script
PROCESS_GRACE_PERIOD = 5        # Seconds to wait for graceful termination
HEARTBEAT_INTERVAL = 30         # Seconds between heartbeat updates

# Logging settings
LOG_ROTATION_SIZE_MB = 25       # Size in MB before rotating logs
LOG_RETENTION_DAYS = 90         # Days to keep old logs

# Detection settings (if applicable)
MOTION_SENSITIVITY = 25         # Detection sensitivity (lower = more sensitive)
#####################################################################

# Path to the current script directory and base deer_deterrant directory
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = Path('/home/rpi5_1/deer_deterrant')
LOGS_DIR = BASE_DIR / "logs" / "animal_coexist_logs"
# Lock file is still in the main logs dir to prevent multiple instances
LOCK_FILE = LOGS_DIR / "deer_deterrent_start.lock"
# PID file will be stored in the run directory (defined in setup_logging)


def should_remove_pid_file():
    """Determine if PID file should be removed on exit"""
    # Get command line arguments without fully parsing them
    has_duration = False
    for arg in sys.argv[1:]:
        if arg.isdigit() or arg.startswith('-d') or arg.startswith('--duration'):
            has_duration = True
            break
    return has_duration


def setup_logging(verbose=False):
    """Set up logging with timestamped directory for each run"""
    # Create logs directory if it doesn't exist
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Check if there's any stray current_run_dir.txt in base directory
    old_file = BASE_DIR / "current_run_dir.txt"
    if old_file.exists():
        print(f"WARNING: Found current_run_dir.txt in base directory: {old_file}")
        print("This may cause confusion with main.py's update_heartbeat(). Consider removing it.")
    
    # Create a timestamped directory for this run
    timestamp = time.strftime("%I-%M_%p_%d-%b-%Y", time.localtime())  # e.g. "09-00_PM_23-Apr-2025"
    run_dir = LOGS_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # Write the current run directory path to a file for other processes to find
    with open(LOGS_DIR / "current_run_dir.txt", 'w') as f:
        f.write(str(run_dir))
    
    log_file = run_dir / "system_control.log"
    
    # Configure logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        filename=log_file,
        level=log_level,
        format='%(asctime)s - [%(levelname)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Add console handler for immediate feedback
    console = logging.StreamHandler()
    console.setLevel(log_level)
    console.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    logging.getLogger('').addHandler(console)
    
    logging.info(f"Created new log directory for this run: {run_dir}")
    
    return run_dir


def acquire_lock():
    """Try to acquire a lock file to prevent multiple instances"""
    try:
        # Ensure directory exists
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        
        lock_fd = open(LOCK_FILE, 'w')
        fcntl.lockf(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except IOError:
        logging.warning("Another instance of animal_coexist.py is already running")
        return None


def release_lock(lock_fd):
    """Release the lock file"""
    if lock_fd:
        try:
            fcntl.lockf(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
            LOCK_FILE.unlink(missing_ok=True)
        except Exception as e:
            logging.error(f"Error releasing lock: {e}")


def stop_existing_processes():
    """Stop any existing instances of the main application"""
    try:
        logging.info("Stopping any existing processes")
        stop_script = SCRIPT_DIR / "stop_system.py"
        
        if not stop_script.exists():
            logging.error(f"Stop script not found at {stop_script}")
            return False
            
        result = subprocess.run(
            ["python3", str(stop_script)], 
            capture_output=True, 
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            logging.info(f"Successfully stopped existing processes: \n\n{result.stdout.strip()}")
            return True
        else:
            logging.warning(f"Issue stopping processes: {result.stderr.strip()}")
            return False
    
    except Exception as e:
        logging.error(f"Failed to stop processes: {e}")
        return False


def write_pid_file(pid, run_dir):
    """Write the process ID to a file for monitoring"""
    try:
        pid_file = run_dir / "main_process.pid"
        with open(pid_file, 'w') as f:
            f.write(str(pid))
        logging.info(f"Wrote PID {pid} to {pid_file}")
        return pid_file
    except Exception as e:
        logging.error(f"Failed to write PID file: {e}")
        return None


def write_heartbeat_file(log_dir):
    """Write current timestamp to heartbeat file in the requested format, appending to history"""
    try:
        # Format timestamp as hh.mm.ss_mm-dd-yyyy
        timestamp = datetime.datetime.now().strftime("%H.%M.%S_%m-%d-%Y")
        
        heartbeat_file = log_dir / "heartbeat"
        # Append to file instead of overwriting
        with open(heartbeat_file, 'a') as f:
            f.write(timestamp + "\n")
        
        # Also update the current run directory file at the root logs dir
        with open(LOGS_DIR / "current_run_dir.txt", 'w') as f:
            f.write(str(log_dir))
            
        logging.debug(f"Appended heartbeat timestamp: {timestamp}")
    except Exception as e:
        logging.error(f"Failed to write heartbeat file: {e}")


def start_main(log_dir, duration=None, view_img=False):
    """Start the main application with output to terminal"""
    # Path to main script
    main_py_path = SCRIPT_DIR / MAIN_SCRIPT
    
    # Verify main script exists
    if not main_py_path.exists():
        logging.error(f"Main script not found at {main_py_path}")
        return False
    
    try:
        # Build command with proper arguments
        command = ["python3", str(main_py_path)]
        if view_img:
            command.append("--view-img")
        
        logging.info(f"Starting main process: {command}")
        
        # Print status message to the terminal
        print("\n" + "="*60)
        print(f"  DEER DETERRENT SYSTEM STARTED")
        print(f"  Script: {main_py_path}")
        print(f"  Log Directory: {log_dir}")
        print(f"  Visualization: {'Enabled' if view_img else 'Disabled'}")
        if duration:
            print(f"  Duration: {duration} seconds")
        else:
            print(f"  Duration: Running indefinitely")
        print("="*60 + "\n")
        
        # Option 1: Direct to terminal (don't handle log file)
        # This is the simplest and most reliable approach
        process = subprocess.Popen(
            command,
            stdout=None,  # Just use current terminal's stdout
            stderr=None,  # Just use current terminal's stderr
            preexec_fn=os.setsid  # Create new process group
        )
        
        # Save the process ID for monitoring in the run directory
        process_pid = process.pid
        pid_file = write_pid_file(process_pid, log_dir)
        
        # Write initial heartbeat
        write_heartbeat_file(log_dir)
        
        logging.info(f"Main process started with PID {process_pid}")
        
        if duration:
            logging.info(f"Running for {duration} seconds")
            
            try:
                # Wait for the specified duration with heartbeat updates
                end_time = time.time() + duration
                while time.time() < end_time and process.poll() is None:
                    # Update heartbeat at specified intervals
                    sleep_time = min(HEARTBEAT_INTERVAL, end_time - time.time())
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                        if process.poll() is None:  # Only update heartbeat if process is still running
                            try:
                                write_heartbeat_file(log_dir)
                            except Exception as e:
                                logging.error(f"Failed to update heartbeat: {e}")
                
                # Try to terminate gracefully if process is still running
                if process.poll() is None:
                    logging.info(f"Duration reached, terminating process {process_pid}")
                    os.killpg(os.getpgid(process_pid), signal.SIGTERM)
                    
                    # Give it time to terminate gracefully
                    for _ in range(PROCESS_GRACE_PERIOD):
                        if process.poll() is not None:
                            break
                        time.sleep(1)
                    
                    # Check if it's still running
                    if process.poll() is None:
                        logging.warning(f"Process {process_pid} didn't terminate gracefully after {PROCESS_GRACE_PERIOD}s, sending SIGKILL")
                        os.killpg(os.getpgid(process_pid), signal.SIGKILL)
                    
                    logging.info("Process terminated after duration")
                
            except Exception as e:
                logging.error(f"Error terminating process: {e}")
                return False
                
        else:
            logging.info("Running indefinitely")
            print("System running indefinitely. Press Ctrl+C to stop.")
            
            # For indefinite mode, wait for the process to complete with heartbeat updates
            try:
                while process.poll() is None:
                    time.sleep(HEARTBEAT_INTERVAL)
                    try:
                        write_heartbeat_file(log_dir)
                    except Exception as e:
                        logging.error(f"Failed to update heartbeat: {e}")
            except KeyboardInterrupt:
                logging.info("Keyboard interrupt received while waiting for process")
                if process.poll() is None:
                    os.killpg(os.getpgid(process_pid), signal.SIGTERM)
                print("\nInterrupted by user. Stopping system...")
            
        return True
        
    except Exception as e:
        logging.error(f"Error starting main process: {e}")
        return False


def cleanup(remove_pid=False):
    """Cleanup function for exit"""
    logging.info("Performing cleanup")
    try:
        # Find current run directory to locate PID file
        if os.path.exists(LOGS_DIR / "current_run_dir.txt"):
            with open(LOGS_DIR / "current_run_dir.txt", 'r') as f:
                current_run_dir = Path(f.read().strip())
                pid_file = current_run_dir / "main_process.pid"
                
                # Only remove PID file if we're in duration mode or handling an error
                if remove_pid and pid_file.exists():
                    pid_file.unlink()
                    logging.info(f"Removed PID file {pid_file}")
                else:
                    logging.info(f"Leaving PID file intact for monitor process")
        else:
            logging.warning("Could not find current run directory file")
    except Exception as e:
        logging.error(f"Error during cleanup: {e}")


def parse_arguments():
    """Parse command line arguments with proper help documentation"""
    parser = argparse.ArgumentParser(
        description='Start the deer deterrent system with various options',
        epilog='Examples:\n'
               '  python3 animal_coexist.py                   # Run indefinitely\n'
               '  python3 animal_coexist.py -d 3600           # Run for 1 hour\n'
               '  python3 animal_coexist.py -v                # Run with visualization\n'
               '  python3 animal_coexist.py -d 600 -v         # Run for 10 minutes with visualization\n',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-d', '--duration', type=int, 
                        help='Duration to run in seconds')
    parser.add_argument('-v', '--view-img', action='store_true',
                        help='Enable visualization of camera feed')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable verbose logging')
    
    # For backward compatibility with positional args
    parser.add_argument('legacy_args', nargs='*', 
                        help=argparse.SUPPRESS)
    
    return parser.parse_args()


def handle_legacy_args(args):
    """Handle legacy positional arguments for backward compatibility"""
    if not args.legacy_args:
        return args
        
    # Process legacy arguments
    for arg in args.legacy_args:
        if arg == 'vi':
            args.view_img = True
            logging.info("Legacy argument 'vi' converted to --view-img")
        else:
            try:
                duration = int(arg)
                args.duration = duration
                logging.info(f"Legacy argument '{arg}' converted to --duration {duration}")
            except ValueError:
                logging.warning(f"Ignoring unrecognized legacy argument: {arg}")
    
    return args


if __name__ == "__main__":
    # Parse arguments
    args = parse_arguments()
    
    # Set up logging
    log_dir = setup_logging(args.verbose)
    
    # Handle legacy arguments
    args = handle_legacy_args(args)
    
    # Register cleanup
    should_cleanup_pid = should_remove_pid_file()
    atexit.register(lambda: cleanup(should_cleanup_pid))
    
    # Try to acquire lock
    lock_fd = acquire_lock()
    if not lock_fd:
        print("\n" + "="*60)
        print("  ERROR: Another instance is already running")
        print("="*60 + "\n")
        sys.exit(1)
    
    try:
        # First stop any existing processes
        stop_existing_processes()
        
        # Start main process
        success = start_main(log_dir, args.duration, args.view_img)
        if not success:
            logging.error("Failed to start main process")
            print("\n" + "="*60)
            print("  ERROR: System startup failed. Check logs for details.")
            print("="*60 + "\n")
            sys.exit(1)
            
        # If running with a duration, we'll wait here until it finishes
        if args.duration:
            print(f"System will stop after {args.duration} seconds")
    
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt")
        print("\n" + "="*60)
        print("  INTERRUPTED: Stopping system...")
        print("="*60 + "\n")
        stop_existing_processes()
    
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}", exc_info=True)
        print("\n" + "="*60)
        print(f"  CRITICAL ERROR: {e}")
        print("="*60 + "\n")
        sys.exit(1)
        
    finally:
        # Release lock file
        release_lock(lock_fd)
