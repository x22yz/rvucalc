#!/usr/bin/env python3

import os
import sys
import json
import re
from datetime import datetime
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

try:
    import pytesseract
    from PIL import Image
    import numpy as np
    DEPENDENCIES_OK = True
except ImportError as e:
    DEPENDENCIES_OK = False
    print(f"Missing dependencies: {e}")
    print("Please run: pip install pillow pytesseract pandas numpy")
    sys.exit(1)

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
            # print(f"Image info: {original_image.size} pixels, mode: {original_image.mode}")
            
            # Use the best method we found: Preprocessed + PSM 11
            processed_image = self.preprocess_image(original_image)
            text = pytesseract.image_to_string(processed_image, config='--psm 11')
            
            # print(f"OCR extracted {len(text)} characters, {len(text.splitlines())} lines")
            return text
            
        except Exception as e:
            print(f"Error processing {image_path}: {e}")
            return ""
    
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
        
        # print(f"Reconstructed {len(reconstructed_lines)} procedure lines from {len(lines)} OCR lines")
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
        """Find procedures in reconstructed text lines with simplified debug output"""
        procedures = []
        unmatched_lines = []
        generic_lines = []
        
        print(f"\n--- Analyzing {len(procedure_lines)} lines from {source_file} ---")
        
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
                    generic_lines.append({
                        'line_num': line_num,
                        'original': line,
                        'cleaned': cleaned_line,
                        'modality': generic_modality
                    })
                    matched = True
            
            # Track unmatched lines for debugging
            if not matched:
                unmatched_lines.append({
                    'line_num': line_num,
                    'original': line,
                    'cleaned': cleaned_line
                })
        
        # Print concise summary
        exact_count = len([p for p in procedures if not p['is_generic']])
        generic_count = len([p for p in procedures if p['is_generic']])
        
        print(f"Results: {exact_count} exact, {generic_count} generic, {len(unmatched_lines)} unmatched")
        
        # Show generic matches that could be made exact
        if generic_lines:
            print(f"\nWARNING: GENERIC MATCHES TO ADD TO DATABASE:")
            for item in generic_lines:
                print(f"  {item['cleaned']}")
        
        # Show unmatched lines for debugging
        if unmatched_lines:
            print(f"\nERROR: COMPLETELY UNMATCHED:")
            for item in unmatched_lines:
                print(f"  {item['cleaned']}")
        
        return procedures
    
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
    
    def print_results(self, results, total_exams, total_wrvus, generic_count):
        """Print minimal results focusing on totals only"""
        print(f"\nSUMMARY: {total_exams} exams, {total_wrvus:.1f} wRVUs")
        if generic_count > 0:
            print(f"({generic_count} generic estimates used)")

    def process_images(self, image_paths):
        """Process images with simplified output"""
        if not image_paths:
            print("No image files provided.")
            return
        
        print(f"Processing {len(image_paths)} image(s)...")
        all_procedures = []
        
        for i, image_path in enumerate(image_paths, 1):
            if not os.path.exists(image_path):
                print(f"File not found: {image_path}")
                continue
            
            print(f"\nIMAGE {i}: {os.path.basename(image_path)}")
            
            # Extract text (suppress detailed OCR output)
            text = self.extract_text_from_image(image_path)
            
            if not text.strip():
                print("ERROR: No text extracted")
                continue
            
            # Reconstruct procedure lines (suppress detailed output)
            procedure_lines = self.reconstruct_procedure_lines(text)
            
            # Find procedures (this will show unmatched lines)
            procedures = self.find_procedures_in_reconstructed_text(procedure_lines, os.path.basename(image_path))
            all_procedures.extend(procedures)
        
        if not all_procedures:
            print("\nERROR: No procedures found in any images.")
            return
        
        # Calculate and show final results
        results, total_exams, total_wrvus, generic_count = self.calculate_wrvus(all_procedures)
        self.print_results(results, total_exams, total_wrvus, generic_count)

def main():
    if not DEPENDENCIES_OK:
        return
    
    calculator = SimpleWRVUCalculator()
    
    print("Simple wRVU Calculator")
    print("="*30)
    
    if len(sys.argv) > 1:
        # Image files provided as command line arguments
        image_paths = sys.argv[1:]
        calculator.process_images(image_paths)
    else:
        # Interactive mode
        print("\nDrag and drop your image files here, then press Enter:")
        print("(Or type the full path to each file, separated by spaces)")
        
        user_input = input().strip()
        
        if not user_input:
            print("No files provided.")
            return
        
        # Handle drag and drop (removes quotes and splits)
        image_paths = []
        parts = user_input.split()
        
        for part in parts:
            # Remove quotes that might be added by drag and drop
            clean_path = part.strip('"\'')
            if os.path.exists(clean_path):
                image_paths.append(clean_path)
            else:
                print(f"File not found: {clean_path}")
        
        calculator.process_images(image_paths)

if __name__ == "__main__":
    main()
