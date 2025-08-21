#!/usr/bin/env python3

import os
import sys
import json
import re
from datetime import datetime
import warnings
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import subprocess
import tempfile
import time
from PIL import ImageGrab, Image
import webbrowser
import urllib.parse
warnings.filterwarnings("ignore", category=DeprecationWarning)

try:
    import pytesseract
    from PIL import Image
    import numpy as np
    DEPENDENCIES_OK = True
except ImportError as e:
    DEPENDENCIES_OK = False
    dependency_error = str(e)

class SimpleWRVUCalculator:
    def __init__(self):
        self.setup_database()
        self.setup_generic_values()
        
    def setup_database(self):
        """Load procedure database from CSV file"""
        self.procedure_db = {}
        
        try:
            import csv
            csv_file = "procedure_database.csv"
            
            if not os.path.exists(csv_file):
                print(f"ERROR: {csv_file} not found!")
                print("Please ensure procedure_database.csv is in the same directory as this script.")
                sys.exit(1)
            
            with open(csv_file, 'r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # Handle potential column name variations
                    name = row.get('name') or row.get('procedure_name') or row.get('Procedure Name')
                    cpt = row.get('cpt') or row.get('CPT') or row.get('cpt_code') or row.get('CPT Code')
                    wrvu = row.get('wrvu') or row.get('WRVU') or row.get('wRVU') or row.get('wRVU Value')
                    
                    if name and cpt and wrvu:
                        self.procedure_db[name.upper().strip()] = {
                            "cpt": str(cpt).strip(),
                            "wrvu": float(wrvu)
                        }
            
            if len(self.procedure_db) == 0:
                print("ERROR: No valid procedures found in CSV file!")
                print("Please check the CSV format and column names.")
                sys.exit(1)
            
            print(f"Loaded {len(self.procedure_db)} procedures from {csv_file}")
                
        except Exception as e:
            print(f"ERROR loading CSV database: {e}")
            print("Please check that procedure_database.csv exists and is properly formatted.")
            sys.exit(1)
    
    def setup_generic_values(self):
        """Generic wRVU values by modality"""
        self.generic_wrvus = {
            "CT": 1.33,
            "MRI": 1.80,
            "XR": 0.25,
            "US": 0.67,
            "MAMMOGRAPHY": 0.7,
            "MG": 0.7,
            "PET": 4.0,
            "NM": 0.85,
            "FL": 0.85,
            "ANGIO": 1.5,
            "DXA": 0.32,
            "IR": 2.5,
            "PROCEDURE": 1.0,
            "OTHER": 1.0
        }
    
    def preprocess_image(self, image):
        """Preprocess image to improve OCR accuracy"""
        import numpy as np
        
        # Convert PIL to numpy array
        img_array = np.array(image)
        
        # Convert to grayscale if needed
        if len(img_array.shape) == 3:
            # Convert RGB to grayscale
            img_array = np.dot(img_array[...,:3], [0.2989, 0.5870, 0.1140])
        
        # Convert back to PIL
        processed_image = Image.fromarray(img_array.astype('uint8'), 'L')
        
        return processed_image
    
    def extract_text_from_image(self, image_path):
        """Extract text from image using best OCR method found"""
        try:
            original_image = Image.open(image_path)
            
            # Use the best method we found: Preprocessed + PSM 11
            processed_image = self.preprocess_image(original_image)
            text = pytesseract.image_to_string(processed_image, config='--psm 11')
            
            return text
            
        except Exception as e:
            raise Exception(f"Error processing {image_path}: {e}")
    
    def clean_pacs_text(self, text):
        """Clean and normalize PACS text for better matching"""
        # Common PACS cleaning patterns
        text = text.upper()
        
        # Replace common PACS abbreviations and clean formatting
        replacements = {
            'CR ': 'XR ',  # Computed Radiography = X-ray
            'CR\t': 'XR ',
            'RF ': 'FL ',  # Radiofluoroscopy = Fluoroscopy
            'RF\t': 'FL ',
            'XA ': 'ANGIO ',  # X-ray Angiography
            'XA\t': 'ANGIO ',
            'BD ': 'DXA ',  # Bone Density
            'BD\t': 'DXA ',
            'PT ': 'PET ',  # Positron Emission Tomography
            'PT\t': 'PET ',
            'MR ': 'MRI ',  # Magnetic Resonance
            'MR\t': 'MRI ',
            'DANGIO': 'DXA',  # OCR error fix
            'MRIHIP': 'MRI HIP',  # OCR error fix
            # Clean up formatting
            '\t': ' ',     # Tabs to spaces
            '_': ' ',      # Underscores to spaces
            '—': ' ',      # Em dashes to spaces
            '-': ' ',      # Hyphens to spaces
            '  ': ' ',     # Double spaces to single
            '   ': ' ',    # Triple spaces to single
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Clean up extra spaces
        while '  ' in text:
            text = text.replace('  ', ' ')
        
        return text.strip()
    
    def reconstruct_procedure_lines(self, text):
        """Reconstruct fragmented procedure lines from OCR output"""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        
        reconstructed_lines = []
        current_procedure = ""
        
        for line in lines:
            # Skip very short lines that are likely fragments
            if len(line) < 3:
                continue
                
            # Date pattern indicates end of procedure line
            if re.search(r'\d{1,2}-\w{3}-\d{4}', line):
                if current_procedure:
                    # Add date/time to current procedure
                    reconstructed_lines.append(f"{current_procedure} {line}")
                    current_procedure = ""
                else:
                    # Line is just a date, skip it
                    continue
            # Number-only lines are usually counts, skip them
            elif line.isdigit():
                continue
            # Modality prefixes (US, CT, MR, etc.) start new procedures
            elif re.match(r'^(US|CT|MR|XR|CR|RF|FL|PT|PET|BD|DXA|NM|IR)', line.upper()):
                if current_procedure:
                    # Save previous procedure if we have one
                    reconstructed_lines.append(current_procedure)
                current_procedure = line
            # Other lines are likely continuations of procedure names
            else:
                if current_procedure:
                    current_procedure += " " + line
                else:
                    current_procedure = line
        
        # Don't forget the last procedure
        if current_procedure:
            reconstructed_lines.append(current_procedure)
        
        return reconstructed_lines
    
    def fuzzy_match(self, proc_name, line):
        """Very strict matching for procedure names"""
        proc_upper = proc_name.upper().strip()
        line_upper = line.upper().strip()
        
        # First try exact substring match (most reliable)
        if proc_upper in line_upper:
            return True
        
        # Extract words, keeping important short words
        proc_words = set(re.findall(r'\b\w+\b', proc_upper))
        line_words = set(re.findall(r'\b\w+\b', line_upper))
        
        # STRICT RULE 1: Modality must match exactly
        modality_mapping = {
            'XR': ['XR'],
            'CT': ['CT'],
            'MRI': ['MRI', 'MR'],
            'US': ['US'],
            'FL': ['FL'],
            'PET': ['PET'],
            'DXA': ['DXA'],
            'NM': ['NM']
        }
        
        proc_modality = None
        line_modality = None
        
        for modality, variants in modality_mapping.items():
            if any(variant in proc_words for variant in variants):
                proc_modality = modality
            if any(variant in line_words for variant in variants):
                line_modality = modality
        
        # If modalities don't match, reject immediately
        if proc_modality and line_modality and proc_modality != line_modality:
            return False
        
        # STRICT RULE 2: Key anatomical words must match exactly
        anatomy_words = {
            'CHEST', 'ABDOMEN', 'PELVIS', 'HEAD', 'BRAIN', 'SPINE', 'LUMBAR', 'CERVICAL', 'THORACIC',
            'KNEE', 'ANKLE', 'SHOULDER', 'ELBOW', 'HIP', 'FOOT', 'HAND', 'WRIST', 'NECK', 'ORBIT'
        }
        
        proc_anatomy = proc_words.intersection(anatomy_words)
        line_anatomy = line_words.intersection(anatomy_words)
        
        # If procedure has anatomy, line must have EXACTLY the same anatomy
        if proc_anatomy and proc_anatomy != line_anatomy:
            return False
        
        # STRICT RULE 3: Contrast information must match
        proc_contrast = set()
        line_contrast = set()
        
        if 'WITH' in proc_words:
            proc_contrast.add('WITH')
        if 'WITHOUT' in proc_words or 'WO' in proc_words:
            proc_contrast.add('WITHOUT')
        if 'WITH' in line_words:
            line_contrast.add('WITH')
        if 'WITHOUT' in line_words or 'WO' in line_words:
            line_contrast.add('WITHOUT')
        
        # If contrast specified, must match
        if proc_contrast and line_contrast and not proc_contrast.intersection(line_contrast):
            return False
        
        # STRICT RULE 4: All significant procedure words must be present
        # Remove very common words that don't add specificity
        common_words = {'AND', 'OR', 'THE', 'OF', 'IN', 'ON', 'AT', 'TO', 'FOR', 'VIEW', 'VIEWS'}
        significant_proc_words = proc_words - common_words
        significant_line_words = line_words - common_words
        
        # At least 90% of significant procedure words must be in the line
        if len(significant_proc_words) > 0:
            matches = len(significant_proc_words.intersection(significant_line_words))
            match_percentage = matches / len(significant_proc_words)
            
            if match_percentage < 0.9:
                return False
        
        return True
    
    def try_generic_match(self, line):
        """Try to match using generic modality patterns"""
        line_upper = line.upper()
        
        modality_patterns = {
            'CT': ['CT ', 'COMPUTED'],
            'MRI': ['MRI ', 'MR ', 'MAGNETIC'],
            'US': ['US ', 'ULTRASOUND', 'ECHO', 'VASCULAR', 'DUPLEX'],
            'XR': ['XR ', 'RADIOGRAPH'],
            'MAMMOGRAPHY': ['MAMMO', 'BREAST', 'MG '],
            'PET': ['PET', 'POSITRON'],
            'NM': ['NM ', 'NUCLEAR', 'BONE SCAN', 'SPECT', 'LUNG SCAN', 'LIVER SCAN'],
            'FL': ['FL ', 'FLUORO', 'FLUOROSCOPY', 'ESOPHAGRAM', 'BARIUM', 'UPPER GI', 'RETROGRADE'],
            'ANGIO': ['ANGIO', 'ANGIOGRAM', 'ANGIOGRAPHY'],
            'DXA': ['DXA', 'BONE DENSITY', 'DEXA'],
            'IR': ['IR ', 'EMBOLIZATION', 'KYPHOPLASTY'],
            'PROCEDURE': ['THORACENTESIS', 'PARACENTESIS']
        }
        
        for modality, patterns in modality_patterns.items():
            if any(pattern in line_upper for pattern in patterns):
                return modality
        
        return None
    
    def find_procedures_in_reconstructed_text(self, procedure_lines, source_file=""):
        """Find procedures in reconstructed text lines"""
        procedures = []
        unmatched_lines = []
        generic_lines = []
        
        for line_num, line in enumerate(procedure_lines, 1):
            if not line or len(line) < 5:
                continue
            
            # Clean PACS text
            cleaned_line = self.clean_pacs_text(line)
            
            # Sort procedures by length (longest first) for better matching
            sorted_procedures = sorted(self.procedure_db.keys(), key=len, reverse=True)
            
            # Try exact matches first
            matched = False
            best_match = None
            best_match_score = 0
            
            for proc_name in sorted_procedures:
                if self.fuzzy_match(proc_name, cleaned_line):
                    match_score = len(proc_name.split())
                    if match_score > best_match_score:
                        best_match = proc_name
                        best_match_score = match_score
            
            if best_match:
                procedures.append({
                    'procedure': best_match,
                    'original_line': line,
                    'cleaned_line': cleaned_line,
                    'is_generic': False,
                    'source': source_file
                })
                matched = True
            
            # Try generic match if no exact match
            if not matched:
                generic_modality = self.try_generic_match(cleaned_line)
                if generic_modality:
                    procedures.append({
                        'procedure': f"GENERIC {generic_modality}",
                        'original_line': line,
                        'cleaned_line': cleaned_line,
                        'is_generic': True,
                        'source': source_file
                    })
                    generic_lines.append(cleaned_line)
                    matched = True
            
            # Track unmatched lines for debugging
            if not matched:
                unmatched_lines.append(cleaned_line)
        
        return procedures, unmatched_lines, generic_lines
    
    def calculate_wrvus(self, procedures):
        """Calculate total wRVUs"""
        # Count procedures
        procedure_counts = {}
        for proc in procedures:
            name = proc['procedure']
            procedure_counts[name] = procedure_counts.get(name, 0) + 1
        
        results = []
        total_exams = 0
        total_wrvus = 0.0
        generic_count = 0
        
        for proc_name, count in procedure_counts.items():
            if proc_name.startswith("GENERIC"):
                modality = proc_name.replace("GENERIC ", "")
                wrvu_each = self.generic_wrvus.get(modality, 1.0)
                cpt = "GENERIC"
                generic_count += count
                is_generic = True
            else:
                proc_data = self.procedure_db[proc_name]
                wrvu_each = proc_data["wrvu"]
                cpt = proc_data["cpt"]
                is_generic = False
            
            total_proc_wrvu = wrvu_each * count
            total_wrvus += total_proc_wrvu
            total_exams += count
            
            results.append({
                'procedure': proc_name,
                'count': count,
                'wrvu_each': wrvu_each,
                'total_wrvu': total_proc_wrvu,
                'cpt': cpt,
                'is_generic': is_generic
            })
        
        return results, total_exams, total_wrvus, generic_count

class WRVUCalculatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("wRVU Calculator")
        self.root.geometry("800x600")
        
        # Check dependencies first
        if not DEPENDENCIES_OK:
            self.show_dependency_error()
            return
        
        self.calculator = SimpleWRVUCalculator()
        self.captured_images = []  # Store captured screenshots
        self.selected_files = []   # Store manually selected files
        self.temp_dir = tempfile.mkdtemp()  # Temp directory for screenshots
        self.unmatched_procedures = []  # Store unmatched procedures for reporting
        
        self.create_widgets()
        
    def show_dependency_error(self):
        """Show dependency error and exit"""
        error_frame = ttk.Frame(self.root, padding="20")
        error_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(error_frame, text="Missing Dependencies", 
                 font=("Arial", 16, "bold")).pack(pady=10)
        
        ttk.Label(error_frame, text=f"Error: {dependency_error}", 
                 wraplength=400).pack(pady=5)
        
        ttk.Label(error_frame, text="Please install required packages:", 
                 font=("Arial", 12, "bold")).pack(pady=(20, 5))
        
        ttk.Label(error_frame, text="pip install pillow pytesseract pandas numpy", 
                 font=("Courier", 10), background="lightgray").pack(pady=5)
        
        ttk.Button(error_frame, text="Exit", 
                  command=self.root.quit).pack(pady=20)
        
    def create_widgets(self):
        """Create the main GUI widgets"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="wRVU Calculator", 
                               font=("Arial", 18, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(pady=(0, 20))
        
        # Screenshot instructions
        screenshot_label = ttk.Label(buttons_frame, 
                                       text="📷 Windows + Shift + S → Select area → Save as file → Add Files",
                                       font=("Arial", 9))
        screenshot_label.pack(side=tk.LEFT, padx=(0, 15))
        
        # Add files button
        self.add_files_btn = ttk.Button(buttons_frame, text="Add Files", 
                                       command=self.add_files,
                                       width=12)
        self.add_files_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Calculate button
        self.calculate_btn = ttk.Button(buttons_frame, text="Calculate", 
                                       command=self.calculate_wrvus,
                                       width=12)
        self.calculate_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Clear button
        self.clear_btn = ttk.Button(buttons_frame, text="Clear All", 
                                   command=self.clear_all,
                                   width=10)
        self.clear_btn.pack(side=tk.LEFT)
        
        # Status frame
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.status_label = ttk.Label(status_frame, text="Ready - capture screenshots or add files")
        self.status_label.pack()
        
        # Results frame
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding="20")
        results_frame.pack(fill=tk.BOTH, expand=True)
        
        # Results display
        self.results_label = ttk.Label(results_frame, text="No calculations yet", 
                                      font=("Arial", 16, "bold"),
                                      anchor="center")
        self.results_label.pack(pady=(0, 20))
        
        # Unmatched procedures section
        unmatched_frame = ttk.LabelFrame(results_frame, text="Unmatched Procedures (for debugging)", padding="10")
        unmatched_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrolled text for unmatched procedures
        self.unmatched_text = scrolledtext.ScrolledText(unmatched_frame, height=8, width=80, wrap=tk.WORD)
        self.unmatched_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Email button for unmatched procedures
        self.email_btn = ttk.Button(unmatched_frame, text="Email Unmatched to Developers", 
                                   command=self.email_unmatched,
                                   state="disabled")
        self.email_btn.pack()
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=(10, 0))
    
    def add_files(self):
        """Add image files manually"""
        filetypes = [
            ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.tiff *.tif"),
            ("All files", "*.*")
        ]
        
        files = filedialog.askopenfilenames(
            title="Select Image Files",
            filetypes=filetypes
        )
        
        if files:
            self.selected_files.extend(files)
            self.update_status()
            messagebox.showinfo("Success", f"Added {len(files)} file(s)")
    
    def update_status(self):
        """Update status display"""
        total_images = len(self.captured_images) + len(self.selected_files)
        if total_images == 0:
            self.status_label.config(text="Ready - capture screenshots or add files")
        else:
            captured_text = f"{len(self.captured_images)} screenshots" if self.captured_images else ""
            files_text = f"{len(self.selected_files)} files" if self.selected_files else ""
            
            if captured_text and files_text:
                status_text = f"Ready to calculate: {captured_text} + {files_text}"
            else:
                status_text = f"Ready to calculate: {captured_text}{files_text}"
            
            self.status_label.config(text=status_text)
    
    def clear_all(self):
        """Clear all captured images and selected files"""
        # Clean up temp files
        for img_path in self.captured_images:
            try:
                os.remove(img_path)
            except:
                pass
        
        self.captured_images = []
        self.selected_files = []
        self.unmatched_procedures = []
        self.update_status()
        self.results_label.config(text="No calculations yet", foreground="black")
        self.unmatched_text.delete(1.0, tk.END)
        self.email_btn.config(state="disabled")
    
    def calculate_wrvus(self):
        """Calculate wRVUs for all images"""
        all_images = self.captured_images + self.selected_files
        
        if not all_images:
            messagebox.showwarning("No Images", "Please capture screenshots or add files first.")
            return
        
        # Start progress bar and run calculation in thread
        self.progress.start()
        self.calculate_btn.config(state="disabled")
        
        thread = threading.Thread(target=self.calculate_thread, args=(all_images,))
        thread.daemon = True
        thread.start()
    
    def calculate_thread(self, image_paths):
        """Calculate wRVUs in background thread"""
        try:
            all_procedures = []
            all_unmatched = []
            all_generic = []
            
            for image_path in image_paths:
                if not os.path.exists(image_path):
                    continue
                
                try:
                    # Extract text
                    text = self.calculator.extract_text_from_image(image_path)
                    
                    if not text.strip():
                        continue
                    
                    # Reconstruct procedure lines
                    procedure_lines = self.calculator.reconstruct_procedure_lines(text)
                    
                    # Find procedures
                    procedures, unmatched, generic = self.calculator.find_procedures_in_reconstructed_text(
                        procedure_lines, os.path.basename(image_path))
                    
                    all_procedures.extend(procedures)
                    all_unmatched.extend(unmatched)
                    all_generic.extend(generic)
                    
                except Exception as e:
                    # Skip failed images silently for clean output
                    continue
            
            if not all_procedures:
                self.update_gui_results("No procedures found", 0, 0.0, [], True)
                return
            
            # Calculate results
            calc_results, total_exams, total_wrvus, generic_count = self.calculator.calculate_wrvus(all_procedures)
            
            # Update GUI with results
            self.update_gui_results(f"{total_exams} Exams | {total_wrvus:.1f} wRVUs", 
                                   total_exams, total_wrvus, all_unmatched, generic_count > 0)
            
        except Exception as e:
            self.update_gui_results(f"Error: {str(e)}", 0, 0.0, [], True)
    
    def update_gui_results(self, results_text, total_exams, total_wrvus, unmatched_list, has_issues):
        """Update GUI with results (called from background thread)"""
        def update():
            self.progress.stop()
            self.calculate_btn.config(state="normal")
            self.results_label.config(text=results_text)
            
            # Color code results
            if total_exams > 0:
                if has_issues:
                    self.results_label.config(foreground="orange")
                else:
                    self.results_label.config(foreground="green")
            else:
                self.results_label.config(foreground="red")
            
            # Update unmatched procedures display
            self.unmatched_text.delete(1.0, tk.END)
            if unmatched_list:
                self.unmatched_procedures = unmatched_list
                unmatched_text = "\n".join(unmatched_list)
                self.unmatched_text.insert(1.0, unmatched_text)
                self.email_btn.config(state="normal")
            else:
                self.unmatched_text.insert(1.0, "No unmatched procedures - all procedures were recognized!")
                self.email_btn.config(state="disabled")
        
        # Schedule GUI update in main thread
        self.root.after(0, update)
    
    def email_unmatched(self):
        """Create simple email for busy radiologists"""
        if not self.unmatched_procedures:
            return
        
        # Developer email address
        dev_email = "anonraddev@gmail.com"
        
        subject = f"wRVU Calculator - {len(self.unmatched_procedures)} Missing Procedures"
        
        body = f"""Hi,

The wRVU Calculator couldn't recognize {len(self.unmatched_procedures)} procedures from my PACS screenshots.

MISSING PROCEDURES:
"""
        
        for i, proc in enumerate(self.unmatched_procedures, 1):
            body += f"{i}. {proc}\n"
        
        body += f"""
Total: {len(self.unmatched_procedures)} procedures
Date: {datetime.now().strftime('%Y-%m-%d')}

Please add these to the database when you get a chance.

Thanks!
(Sent from wRVU Calculator)
"""
        
        mailto_url = f"mailto:{dev_email}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
        
        try:
            webbrowser.open(mailto_url)
            # Show simple confirmation
            messagebox.showinfo("Email Ready", 
                              "Your email is ready to send!\n\n" +
                              "Just click 'Send' in your email program.")
        except Exception as e:
            # Hospital systems might block webbrowser, so show fallback
            self.show_copy_paste_option(dev_email, subject, body)

    def show_copy_paste_option(self, email, subject, body):
        """Fallback for locked-down hospital systems"""
        email_window = tk.Toplevel(self.root)
        email_window.title("Email Information")
        email_window.geometry("500x400")
        
        ttk.Label(email_window, 
                 text="Copy this information and send it via email:", 
                 font=("Arial", 11, "bold")).pack(pady=10)
        
        # Email details in a text box
        email_text = scrolledtext.ScrolledText(email_window, wrap=tk.WORD, height=15)
        email_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        
        full_email = f"To: {email}\nSubject: {subject}\n\n{body}"
        email_text.insert(1.0, full_email)
        
        # Make it easy to select all and copy
        def select_all():
            email_text.tag_add(tk.SEL, "1.0", tk.END)
            email_text.mark_set(tk.INSERT, "1.0")
            email_text.see(tk.INSERT)
        
        button_frame = ttk.Frame(email_window)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Select All", command=select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=email_window.destroy).pack(side=tk.LEFT, padx=5)
        
        # Auto-select all text for easy copying
        email_window.after(100, select_all)

def main():
    root = tk.Tk()
    
    # Configure style for better appearance
    style = ttk.Style()
    
    # Try to use a modern theme
    try:
        style.theme_use('vista')  # Windows
    except:
        try:
            style.theme_use('clam')  # Cross-platform
        except:
            pass  # Use default theme
    
    app = WRVUCalculatorGUI(root)
    
    # Center the window
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")
    
    root.mainloop()

if __name__ == "__main__":
    main()