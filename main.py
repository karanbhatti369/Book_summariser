import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
from summarize import process_book
from googletrans import Translator

def browse_files():
    filename = filedialog.askopenfilename(
        initialdir="/",
        title="Select a File",
        filetypes=(("PDF files", "*.pdf"), ("all files", "*.*")),
    )
    pdf_path.set(filename)

def summarize_book():
    book_url = url_entry.get()
    pdf_file = pdf_path.get()
    target_language = language_combo.get()
    if not book_url and not pdf_file:
        messagebox.showerror("Error", "Please enter a book URL or upload a PDF file.")
        return

    # Start the loader
    start_loader()

    # Use a thread to run the summary generation so the UI remains responsive
    threading.Thread(target=generate_summary, args=(book_url, pdf_file, target_language)).start()

def generate_summary(book_url, pdf_file, target_language):
    try:
        summary = process_book(book_url=book_url, pdf_path=pdf_file)
        if target_language != "English":
            summary = translate_text(summary, target_language)
        show_summary(summary)
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")
    finally:
        stop_loader()

def translate_text(text, target_language):
    translator = Translator()
    translation = translator.translate(text, dest=target_language)
    return translation.text

def start_loader():
    loader.pack(pady=10)
    loader.start()

def stop_loader():
    loader.stop()
    loader.pack_forget()

def show_summary(summary):
    result_window = tk.Toplevel(window)
    result_window.title("Summary")
    result_window.geometry("600x400")
    result_text = tk.Text(result_window, wrap=tk.WORD, padx=10, pady=10, font=("Helvetica", 12))
    result_text.insert(tk.END, summary)
    result_text.config(state=tk.DISABLED)
    result_text.pack(expand=True, fill=tk.BOTH)

# Initialize Tkinter window
window = tk.Tk()
window.title("AI Book Summarizer")
window.geometry("400x500")
window.configure(bg="#2c2c2c")

# Style variables
bg_color = "#2c2c2c"
fg_color = "#ffffff"
button_bg = "#4CAF50"
button_fg = "#BD0B49"
font_style = ("Helvetica", 12)

# URL Input
tk.Label(window, text="Your AI Book Summarizer", font=("Helvetica", 20, "bold"), bg=bg_color, fg=fg_color).pack(pady=10)
tk.Label(window, text="Help you to catch up faster!", font=("Helvetica", 15), bg=bg_color, fg=fg_color).pack(pady=5)
tk.Label(window, text="Enter Book URL:", font=font_style, bg=bg_color, fg=fg_color).pack(pady=5)
url_entry = tk.Entry(window, width=50, font=font_style, bg="#444444", fg=fg_color, insertbackground=fg_color)
url_entry.pack(pady=5)

# PDF Upload
tk.Label(window, text="Or Upload a PDF:", font=font_style, bg=bg_color, fg=fg_color).pack(pady=5)
pdf_path = tk.StringVar()
pdf_entry = tk.Entry(window, textvariable=pdf_path, width=50, font=font_style, bg="#444444", fg=fg_color, insertbackground=fg_color)
pdf_entry.pack(pady=5)
browse_button = tk.Button(window, text="Browse", command=browse_files, bg=button_bg, fg=button_fg, font=font_style)
browse_button.pack(pady=10)

# Language Selection
tk.Label(window, text="Select Language:", font=font_style, bg=bg_color, fg=fg_color).pack(pady=5)
language_combo = ttk.Combobox(window, values=["English", "French", "Hindi", "Italian"], font=font_style)
language_combo.current(0)
language_combo.pack(pady=5)

# Loading Spinner
loader = ttk.Progressbar(window, mode='indeterminate', length=200)

# Generate Summary Button
generate_button = tk.Button(window, text="Generate Summary", command=summarize_book, bg=button_bg, fg=button_fg, font=font_style)
generate_button.pack(pady=10)

# Adding hover effect to buttons
def on_enter(event):
    event.widget.config(bg="#45a049")

def on_leave(event):
    event.widget.config(bg=button_bg)

browse_button.bind("<Enter>", on_enter)
browse_button.bind("<Leave>", on_leave)
generate_button.bind("<Enter>", on_enter)
generate_button.bind("<Leave>", on_leave)

window.mainloop()
