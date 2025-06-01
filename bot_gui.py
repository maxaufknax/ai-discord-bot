import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import subprocess
import os
import threading
import queue

CONFIG_FILE = 'config.json'
BOT_SCRIPT = 'enhanced_bot.py' # Assuming it's in the same directory

class BotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Discord Bot Control Panel")
        self.root.geometry("600x500") # Adjusted size

        self.bot_process = None
        self.log_queue = queue.Queue()

        # Styling
        style = ttk.Style()
        style.theme_use('clam') # Using a theme that tends to look better
        style.configure("TLabel", padding=5, font=('Helvetica', 10))
        style.configure("TButton", padding=5, font=('Helvetica', 10))
        style.configure("TEntry", padding=5, font=('Helvetica', 10))
        style.configure("TFrame", padding=10)

        # Main frame
        main_frame = ttk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Configuration Frame ---
        config_frame = ttk.LabelFrame(main_frame, text="Configuration")
        config_frame.pack(fill=tk.X, padx=10, pady=5)

        # Discord Token
        ttk.Label(config_frame, text="Discord Token:").grid(row=0, column=0, sticky=tk.W)
        self.discord_token_var = tk.StringVar()
        self.discord_token_entry = ttk.Entry(config_frame, textvariable=self.discord_token_var, show='*', width=50)
        self.discord_token_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)

        # Gemini API Key
        ttk.Label(config_frame, text="Gemini API Key:").grid(row=1, column=0, sticky=tk.W)
        self.gemini_api_key_var = tk.StringVar()
        self.gemini_api_key_entry = ttk.Entry(config_frame, textvariable=self.gemini_api_key_var, show='*', width=50)
        self.gemini_api_key_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)

        # Knowledge Base Directory
        ttk.Label(config_frame, text="Knowledge Dir:").grid(row=2, column=0, sticky=tk.W)
        self.kb_dir_var = tk.StringVar()
        self.kb_dir_entry = ttk.Entry(config_frame, textvariable=self.kb_dir_var, width=40) # Make it slightly narrower
        self.kb_dir_entry.grid(row=2, column=1, padx=(5,0), pady=5, sticky=tk.EW)
        self.browse_kb_button = ttk.Button(config_frame, text="Browse...", command=self.browse_kb_dir)
        self.browse_kb_button.grid(row=2, column=2, padx=(5,5), pady=5, sticky=tk.W)

        config_frame.grid_columnconfigure(1, weight=1) # Allow entry to expand

        # Save Button
        self.save_button = ttk.Button(config_frame, text="Save Configuration", command=self.save_config)
        self.save_button.grid(row=3, column=0, columnspan=3, pady=10) # Span across 3 columns

        # --- Control Frame ---
        control_frame = ttk.LabelFrame(main_frame, text="Bot Control")
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        self.start_button = ttk.Button(control_frame, text="Start Bot", command=self.start_bot)
        self.start_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.stop_button = ttk.Button(control_frame, text="Stop Bot", command=self.stop_bot, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5, pady=5)

        # --- Status and Log Frame ---
        status_log_frame = ttk.LabelFrame(main_frame, text="Status & Logs")
        status_log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.status_var = tk.StringVar(value="Bot Offline")
        status_label = ttk.Label(status_log_frame, textvariable=self.status_var, font=('Helvetica', 10, 'bold'))
        status_label.pack(pady=5, anchor=tk.W)

        self.log_text = tk.Text(status_log_frame, height=10, state=tk.DISABLED, font=('Courier New', 9), wrap=tk.WORD)
        log_scrollbar = ttk.Scrollbar(status_log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)


        self.load_config()
        self.check_bot_script()
        self.root.after(100, self.process_log_queue) # Start polling log queue

    def check_bot_script(self):
        if not os.path.exists(BOT_SCRIPT):
            messagebox.showerror("Error", f"{BOT_SCRIPT} not found in the current directory. Please ensure it exists.")
            self.start_button.config(state=tk.DISABLED)
            self.log_message(f"Error: {BOT_SCRIPT} not found. Bot cannot be started.")


    def log_message(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message.strip() + '\n')
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def process_log_queue(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                if line is None: # Sentinel to stop
                    return
                self.log_message(line)
        except queue.Empty:
            pass
        self.root.after(100, self.process_log_queue)


    def _stream_watcher(self, identifier, stream):
        for line in iter(stream.readline, ''):
            self.log_queue.put(f"[{identifier}] {line.decode('utf-8', errors='replace')}")
        stream.close()
        if identifier == "stdout": # Signal end of process output
             self.log_queue.put(None) # Sentinel for process_log_queue if needed, or handle bot stop state

    def load_config(self):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config_data = json.load(f)
            self.discord_token_var.set(config_data.get('DISCORD_TOKEN', ''))
            self.gemini_api_key_var.set(config_data.get('GEMINI_API_KEY', ''))
            self.kb_dir_var.set(config_data.get('KNOWLEDGE_BASE_DIR', 'user_knowledge/')) # Default if not in config
            self.log_message(f"Configuration loaded from {CONFIG_FILE}")
        except FileNotFoundError:
            self.log_message(f"{CONFIG_FILE} not found. Please configure and save.")
            self.kb_dir_var.set('user_knowledge/') # Default for new config
        except json.JSONDecodeError:
            messagebox.showerror("Error", f"Error decoding {CONFIG_FILE}. Check its format.")
            self.log_message(f"Error decoding {CONFIG_FILE}.")

    def save_config(self):
        config_data = {
            'DISCORD_TOKEN': self.discord_token_var.get(),
            'GEMINI_API_KEY': self.gemini_api_key_var.get(),
            'KNOWLEDGE_BASE_DIR': self.kb_dir_var.get()
        }
        if not config_data['DISCORD_TOKEN'] or not config_data['GEMINI_API_KEY']:
            messagebox.showwarning("Warning", "Discord Token and Gemini API Key are required.")
            return
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_data, f, indent=4)
            self.log_message(f"Configuration saved to {CONFIG_FILE}")
            messagebox.showinfo("Success", "Configuration saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {e}")
            self.log_message(f"Error saving config: {e}")

    def browse_kb_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.kb_dir_var.set(directory)

    def start_bot(self):
        if not os.path.exists(BOT_SCRIPT):
            messagebox.showerror("Error", f"{BOT_SCRIPT} not found.")
            return

        # Ensure config is saved before starting
        self.save_config()
        # Quick check if critical fields are empty after save attempt
        if not self.discord_token_var.get() or not self.gemini_api_key_var.get():
             self.log_message("Bot cannot start: Discord Token or Gemini API Key is missing in configuration.")
             messagebox.showerror("Error", "Discord Token or Gemini API Key is missing. Please save the configuration.")
             return

        self.log_message("Attempting to start the bot...")
        try:
            # For Windows, `creationflags=subprocess.CREATE_NO_WINDOW` can hide the console.
            # For Linux/macOS, this isn't needed.
            kwargs = {'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE, 'text': False} # text=False for binary streams
            if os.name == 'nt':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

            self.bot_process = subprocess.Popen(['python', '-u', BOT_SCRIPT], **kwargs)

            threading.Thread(target=self._stream_watcher, args=('stdout', self.bot_process.stdout), daemon=True).start()
            threading.Thread(target=self._stream_watcher, args=('stderr', self.bot_process.stderr), daemon=True).start()

            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.status_var.set("Bot Running")
            self.log_message(f"Bot process started (PID: {self.bot_process.pid}).")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start bot: {e}")
            self.log_message(f"Error starting bot: {e}")
            self.status_var.set("Bot Failed to Start")

    def stop_bot(self):
        if self.bot_process and self.bot_process.poll() is None: # Check if process exists and is running
            self.log_message("Attempting to stop the bot...")
            try:
                self.bot_process.terminate() # More forceful, consider .send_signal(signal.SIGINT) for graceful
                self.bot_process.wait(timeout=5) # Wait for process to terminate
                self.log_message(f"Bot process {self.bot_process.pid} terminated.")
            except subprocess.TimeoutExpired:
                self.log_message(f"Bot process {self.bot_process.pid} did not terminate in time, killing.")
                self.bot_process.kill()
                self.log_message(f"Bot process {self.bot_process.pid} killed.")
            except Exception as e:
                self.log_message(f"Error stopping bot: {e}")
                # messagebox.showerror("Error", f"Error stopping bot: {e}")
        else:
            self.log_message("Bot process not running or already stopped.")

        self.bot_process = None
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("Bot Offline")

    def on_closing(self):
        if self.bot_process and self.bot_process.poll() is None:
            if messagebox.askyesno("Confirm", "Bot is running. Do you want to stop it and exit?"):
                self.stop_bot()
            else:
                return # Don't close
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    app = BotGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing) # Handle window close button
    root.mainloop()
