"""
Progress Manager for Speech Dataset Creator

Provides a clean terminal UI with multiple progress bars for different processing stages.
"""

from rich.console import Console
from rich.progress import Progress, TaskID, BarColumn, TextColumn, TimeRemainingColumn, MofNCompleteColumn
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from typing import Optional, Dict, Any
import sys
import io
from contextlib import redirect_stdout, redirect_stderr


class ProgressManager:
    """Manages multiple progress bars for the speech dataset processing pipeline."""
    
    def __init__(self):
        self.console = Console()
        self.progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TimeRemainingColumn(),
            console=self.console,
            expand=False
        )
        
        # Task IDs for different progress levels
        self.overall_task: Optional[TaskID] = None
        self.file_task: Optional[TaskID] = None
        self.split_task: Optional[TaskID] = None
        self.step_task: Optional[TaskID] = None
        
        # Progress state
        self.is_running = False
        self.live: Optional[Live] = None
        
        # Capture stdout/stderr for logging
        self.log_buffer = io.StringIO()
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        
    def start(self):
        """Start the progress display."""
        if self.is_running:
            return
            
        self.is_running = True
        
        # Create the live display
        layout = Layout()
        layout.split(
            Layout(name="progress", size=6),
            Layout(name="logs")
        )
        
        layout["progress"].update(Panel(self.progress, title="Processing Progress"))
        layout["logs"].update(Panel("", title="Logs", border_style="dim"))
        
        self.live = Live(layout, console=self.console, refresh_per_second=10)
        self.live.start()
        
        # Redirect stdout/stderr to capture logs
        sys.stdout = self.log_buffer
        sys.stderr = self.log_buffer
        
    def stop(self):
        """Stop the progress display."""
        if not self.is_running:
            return
            
        # Restore stdout/stderr
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        
        if self.live:
            self.live.stop()
            
        self.is_running = False
        
        # Print any remaining logs
        logs = self.log_buffer.getvalue()
        if logs.strip():
            self.console.print(logs.strip())
            
    def init_overall_progress(self, total_steps: int, description: str = "Overall Progress"):
        """Initialize the overall progress bar."""
        if self.overall_task is not None:
            self.progress.remove_task(self.overall_task)
        self.overall_task = self.progress.add_task(description, total=total_steps)
        
    def init_file_progress(self, total_files: int, description: str = "Processing Files"):
        """Initialize the file progress bar."""
        if self.file_task is not None:
            self.progress.remove_task(self.file_task)
        self.file_task = self.progress.add_task(description, total=total_files)
        
    def init_split_progress(self, total_splits: int, description: str = "Processing Splits"):
        """Initialize the split progress bar."""
        if self.split_task is not None:
            self.progress.remove_task(self.split_task)
        if total_splits > 0:
            self.split_task = self.progress.add_task(description, total=total_splits)
        else:
            self.split_task = None
            
    def init_step_progress(self, total_steps: int, description: str = "Processing Steps"):
        """Initialize the step progress bar."""
        if self.step_task is not None:
            self.progress.remove_task(self.step_task)
        if total_steps > 0:
            self.step_task = self.progress.add_task(description, total=total_steps)
        else:
            self.step_task = None
            
    def update_overall(self, advance: int = 1, description: Optional[str] = None):
        """Update the overall progress."""
        if self.overall_task is not None:
            self.progress.update(self.overall_task, advance=advance, description=description)
            
    def update_file(self, advance: int = 1, description: Optional[str] = None):
        """Update the file progress."""
        if self.file_task is not None:
            self.progress.update(self.file_task, advance=advance, description=description)
            
    def update_split(self, advance: int = 1, description: Optional[str] = None):
        """Update the split progress."""
        if self.split_task is not None:
            self.progress.update(self.split_task, advance=advance, description=description)
            
    def update_step(self, advance: int = 1, description: Optional[str] = None):
        """Update the step progress."""
        if self.step_task is not None:
            self.progress.update(self.step_task, advance=advance, description=description)
            
    def set_overall_complete(self, completed: int, description: Optional[str] = None):
        """Set the overall progress to a specific completion value."""
        if self.overall_task is not None:
            self.progress.update(self.overall_task, completed=completed, description=description)
            
    def set_file_complete(self, completed: int, description: Optional[str] = None):
        """Set the file progress to a specific completion value."""
        if self.file_task is not None:
            self.progress.update(self.file_task, completed=completed, description=description)
            
    def set_split_complete(self, completed: int, description: Optional[str] = None):
        """Set the split progress to a specific completion value."""
        if self.split_task is not None:
            self.progress.update(self.split_task, completed=completed, description=description)
            
    def set_step_complete(self, completed: int, description: Optional[str] = None):
        """Set the step progress to a specific completion value."""
        if self.step_task is not None:
            self.progress.update(self.step_task, completed=completed, description=description)
            
    def print_log(self, message: str):
        """Print a log message that will appear below the progress bars."""
        if self.is_running:
            # Store the message in buffer to be displayed
            self.log_buffer.write(f"{message}\n")
            self.log_buffer.flush()
            
            # Update the logs panel with just recent messages
            if self.live and hasattr(self.live, 'renderable'):
                logs = self.log_buffer.getvalue()
                # Keep only the last 50 lines to prevent memory issues
                log_lines = logs.strip().split('\n')
                if len(log_lines) > 50:
                    # Keep the most recent 30 lines for display, but preserve more in buffer
                    display_lines = log_lines[-30:]
                    # Reset buffer with the last 50 lines
                    self.log_buffer = io.StringIO()
                    self.log_buffer.write('\n'.join(log_lines[-50:]) + '\n')
                else:
                    display_lines = log_lines
                
                # Update the logs panel - only show recent lines
                layout = self.live.renderable
                if hasattr(layout, '__getitem__'):
                    # Show only the last 15 lines in the display
                    display_text = '\n'.join(display_lines[-15:]) if display_lines else ""
                    layout["logs"].update(Panel(display_text, title="Recent Logs", border_style="dim"))
        else:
            # If not running, print directly
            self.console.print(message)
            
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()