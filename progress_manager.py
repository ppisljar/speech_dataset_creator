"""
Progress Manager for Speech Dataset Creator

Uses rich.live for split-screen display with fixed progress bars and scrollable logs.
"""

from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, MofNCompleteColumn
from rich.text import Text
import sys
from typing import Optional
import threading
import time


class ProgressManager:
    """Split-screen progress manager with fixed progress bars and scrollable logs."""
    
    def __init__(self):
        self.console = Console()
        
        # Progress tracking
        self.progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TimeRemainingColumn(),
            console=self.console,
            expand=False
        )
        
        # Task IDs
        self.overall_task = None
        self.file_task = None
        self.module_task = None
        self.step_task = None
        
        # Layout and live display
        self.layout = None
        self.live = None
        self.is_running = False
        
        # Log messages
        self.log_messages = []
        self.max_log_lines = 20
        
        # Thread lock for updates
        self.lock = threading.Lock()
        
    def start(self):
        """Start the progress manager with split screen."""
        self.is_running = True
        
        # Create layout
        self.layout = Layout()
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="progress", size=8),
            Layout(name="logs")
        )
        
        # Set up header
        self.layout["header"].update(
            Panel(
                Text("SPEECH DATASET CREATOR - PROCESSING", style="bold white"),
                style="blue"
            )
        )
        
        # Set up progress area
        self.layout["progress"].update(
            Panel(self.progress, title="Progress", border_style="green")
        )
        
        # Set up logs area
        self.layout["logs"].update(
            Panel("", title="Processing Log", border_style="dim")
        )
        
        # Start live display
        self.live = Live(self.layout, console=self.console, refresh_per_second=4)
        self.live.start()
        
    def stop(self):
        """Stop the progress manager."""
        if self.live:
            self.live.stop()
            
        if self.is_running:
            self.console.print("\n[green]PROCESSING COMPLETED[/green]")
        self.is_running = False
        
    def init_overall_progress(self, total_steps: int, description: str = "Overall Progress"):
        """Initialize the overall progress bar."""
        with self.lock:
            if self.overall_task is not None:
                self.progress.remove_task(self.overall_task)
            self.overall_task = self.progress.add_task(description, total=total_steps)
        
    def init_file_progress(self, total_files: int, description: str = "Processing Files"):
        """Initialize the file progress bar."""
        with self.lock:
            if self.file_task is not None:
                self.progress.remove_task(self.file_task)
            self.file_task = self.progress.add_task(description, total=total_files)
        
    def init_split_progress(self, total_splits: int, description: str = "Processing Module"):
        """Initialize module progress bar."""
        with self.lock:
            if self.module_task is not None:
                self.progress.remove_task(self.module_task)
            if total_splits > 0:
                self.module_task = self.progress.add_task(description, total=total_splits)
            
    def init_step_progress(self, total_steps: int, description: str = "Current Step"):
        """Initialize step progress bar."""
        with self.lock:
            if self.step_task is not None:
                self.progress.remove_task(self.step_task)
            if total_steps > 0:
                self.step_task = self.progress.add_task(description, total=total_steps)
            
    def update_overall(self, advance: int = 1, description: Optional[str] = None):
        """Update the overall progress."""
        with self.lock:
            if self.overall_task is not None:
                self.progress.update(self.overall_task, advance=advance, description=description)
            
    def update_file(self, advance: int = 1, description: Optional[str] = None):
        """Update the file progress."""
        with self.lock:
            if self.file_task is not None:
                self.progress.update(self.file_task, advance=advance, description=description)
            
    def update_split(self, advance: int = 1, description: Optional[str] = None):
        """Update module progress."""
        with self.lock:
            if self.module_task is not None:
                self.progress.update(self.module_task, advance=advance, description=description)
            
    def update_step(self, advance: int = 1, description: Optional[str] = None):
        """Update step progress."""
        with self.lock:
            if self.step_task is not None:
                self.progress.update(self.step_task, advance=advance, description=description)
            
    def set_overall_complete(self, completed: int, description: Optional[str] = None):
        """Set the overall progress to a specific completion value."""
        with self.lock:
            if self.overall_task is not None:
                self.progress.update(self.overall_task, completed=completed, description=description)
            
    def set_file_complete(self, completed: int, description: Optional[str] = None):
        """Set the file progress to a specific completion value."""
        with self.lock:
            if self.file_task is not None:
                self.progress.update(self.file_task, completed=completed, description=description)
            
    def set_split_complete(self, completed: int, description: Optional[str] = None):
        """Set module progress to a specific completion value."""
        with self.lock:
            if self.module_task is not None:
                self.progress.update(self.module_task, completed=completed, description=description)
            
    def set_step_complete(self, completed: int, description: Optional[str] = None):
        """Set step progress to a specific completion value."""
        with self.lock:
            if self.step_task is not None:
                self.progress.update(self.step_task, completed=completed, description=description)
            
    def print_log(self, message: str):
        """Add a log message to the scrollable log area."""
        with self.lock:
            # Add timestamp
            timestamp = time.strftime("%H:%M:%S")
            formatted_message = f"[dim]{timestamp}[/dim] {message}"
            
            self.log_messages.append(formatted_message)
            
            # Keep only recent messages
            if len(self.log_messages) > self.max_log_lines:
                self.log_messages = self.log_messages[-self.max_log_lines:]
            
            # Update logs panel
            if self.layout and self.is_running:
                log_text = "\n".join(self.log_messages)
                self.layout["logs"].update(
                    Panel(log_text, title="Processing Log", border_style="dim")
                )
            
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()