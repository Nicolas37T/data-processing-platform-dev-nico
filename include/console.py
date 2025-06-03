from rich.console import Console

console = Console()

def info_print(message):
    console.print(f'[bold blue][INFO][/bold blue] {message}')

def error_print(message):
    console.print(f'[bold red][ERROR][/bold red] {message}')

def success_print(message):
    console.print(f"[bold green][SUCCESS][/bold green] {message}")