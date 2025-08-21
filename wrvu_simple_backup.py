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
        """Setup 2024 wRVU database with all missing procedures added"""
        self.procedure_db = {
            # US procedures
            "US VENOUS LOWER EXTREMITY DUPLEX BILATERAL": {"cpt": "93971", "wrvu": 0.7},
            "US VENOUS LOWER EXTREMITY DUPLEX": {"cpt": "93970", "wrvu": 0.45},
            "VASCULAR VEINS LOWER EXTREMITY DUPLEX": {"cpt": "93970", "wrvu": 0.45},
            "US RENAL KIDNEY": {"cpt": "76770", "wrvu": 0.58},
            "US RENAL": {"cpt": "76770", "wrvu": 0.58},
            "US OB LESS THAN 14 WEEKS": {"cpt": "76815", "wrvu": 0.85},
            "US OB GREATER THAN 14 WEEKS": {"cpt": "76805", "wrvu": 0.99},
            "US OB LESS THAN 14 WEEKS TRANSABDOMINAL": {"cpt": "76815", "wrvu": 0.85},
            "US OB GREATER THAN 14 WEEKS TRANSABDOMINAL": {"cpt": "76805", "wrvu": 0.99},
            "US OB FOLLOW UP PER FETUS": {"cpt": "76815", "wrvu": 0.85},
            "US NON OB TRANSVAGINAL": {"cpt": "76830", "wrvu": 0.69},
            "US OB TRANSVAGINAL": {"cpt": "76830", "wrvu": 0.69},
            "US PARACENTESIS": {"cpt": "76942", "wrvu": 0.67},
            "US BIOPSY": {"cpt": "76942", "wrvu": 0.67},
            "US LEG RT VENOUS": {"cpt": "93970", "wrvu": 0.45},
            "US LEG LT VENOUS": {"cpt": "93970", "wrvu": 0.45},
            "US ABDOMEN LIMITED": {"cpt": "76705", "wrvu": 0.59},
            "US LIMITED ABDOMEN": {"cpt": "76705", "wrvu": 0.59},
            "US COMPLETE ABDOMEN": {"cpt": "76700", "wrvu": 0.81},
            "US THYROID PARATHYROID NECK": {"cpt": "76536", "wrvu": 0.56},
            "US SCROTUM AND TESTICLES": {"cpt": "76870", "wrvu": 0.64},
            "US RETROPERITONEAL LIMITED": {"cpt": "76770", "wrvu": 0.58},
            "US RETROPERITONEAL COMPLETE": {"cpt": "76770", "wrvu": 0.58},
            "US PELVIS COMPLETE": {"cpt": "76856", "wrvu": 0.69},
            "US PELVIS COMPLETE AND US NON OB TRANSVAGINAL": {"cpt": "76856", "wrvu": 0.69},
            "US BREAST BILATERAL LIMITED": {"cpt": "76641", "wrvu": 0.69},
            
            # CT procedures
            "CT ENTEROGRAPHY ABDOMEN AND PELVIS WITH CONTRAST": {"cpt": "74177", "wrvu": 1.82},
            "CT ABDOMEN PELVIS WITH AND WITHOUT CONTRAST": {"cpt": "74178", "wrvu": 2.01},
            "CT ABDOMEN PELVIS WITH CONTRAST": {"cpt": "74177", "wrvu": 1.82},
            "CT ABDOMEN PELVIS WITHOUT CONTRAST": {"cpt": "74176", "wrvu": 1.74},
            "CT PELVIS WITHOUT CONTRAST": {"cpt": "72192", "wrvu": 1.19},
            "CT CHEST WITH CONTRAST": {"cpt": "71260", "wrvu": 1.24},
            "CT CHEST WITHOUT CONTRAST": {"cpt": "71250", "wrvu": 1.02},
            "CT CHEST HIGH RESOLUTION": {"cpt": "71250", "wrvu": 1.02},
            "CT ANGIOGRAM CHEST PULMONARY EMBOLISM": {"cpt": "71275", "wrvu": 1.82},
            "CT ANGIOGRAM CHEST ABDOMEN PELVIS": {"cpt": "74174", "wrvu": 2.2},
            "CT ANGIOGRAM CHEST WITH AND OR WITHOUT CONTRAST": {"cpt": "71275", "wrvu": 1.82},
            "CT ANGIOGRAM ABDOMINAL AORTA AND BILATERAL ILIOFEM": {"cpt": "74175", "wrvu": 1.82},
            "CT ANGIOGRAM ABDOMEN WITH AND OR WITHOUT CONTRAST": {"cpt": "74174", "wrvu": 1.82},
            "CT ANGIOGRAM HEAD WITH WO CONTRAST ACUTE STROKE": {"cpt": "70496", "wrvu": 1.75},
            "CT ANGIOGRAM NECK WITH WO CONTRAST ACUTE STROKE": {"cpt": "70498", "wrvu": 1.75},
            "CT HEAD WITHOUT CONTRAST": {"cpt": "70450", "wrvu": 0.85},
            "CT HEAD WITHOUT CONTRAST ACUTE STROKE": {"cpt": "70450", "wrvu": 0.85},
            "CT HEAD WITH AND WITHOUT CONTRAST": {"cpt": "70470", "wrvu": 1.27},
            "CT LOWER EXTREMITY WITHOUT CONTRAST": {"cpt": "73700", "wrvu": 1.33},
            "CT LOWER EXTREMITY WITHOUT CONTRAST LEFT": {"cpt": "73700", "wrvu": 1.33},
            "CT UPPER EXTREMITY WITHOUT CONTRAST": {"cpt": "73200", "wrvu": 1.33},
            "CT UPPER EXTREMITY WITHOUT CONTRAST RIGHT": {"cpt": "73200", "wrvu": 1.33},
            "CT HEART CALCIUM SCORE WITHOUT CONTRAST": {"cpt": "75571", "wrvu": 0.58},
            "CT ORBITS SELLA IAC WITHOUT CONTRAST": {"cpt": "70481", "wrvu": 1.13},
            "CT ORBITS SELLA OR IAC WITHOUT CONTRAST": {"cpt": "70481", "wrvu": 1.13},
            "CT MAXILLOFACIAL WITHOUT CONTRAST": {"cpt": "70486", "wrvu": 0.85},
            "CT LUMBAR SPINE WITHOUT CONTRAST": {"cpt": "72131", "wrvu": 1.0},
            "CT LUNG SCREEN PROTOCOL LOW DOSE INITIAL BASELINE": {"cpt": "71271", "wrvu": 1.02},
            "CT C SPINE SPINE WO CON": {"cpt": "72125", "wrvu": 1.0},
            "CT THORACIC SPINE WITHOUT CONTRAST": {"cpt": "72128", "wrvu": 1.0},
            "CT SOFT TISSUE NECK WITH CONTRAST": {"cpt": "70491", "wrvu": 1.38},
            
            # MRI procedures
            "MRI ABDOMEN WITH AND WITHOUT CONTRAST": {"cpt": "74183", "wrvu": 2.27},
            "MRI BRAIN WITH AND WITHOUT CONTRAST": {"cpt": "70554", "wrvu": 2.29},
            "MRI BRAIN WITHOUT CONTRAST": {"cpt": "70551", "wrvu": 1.48},
            "MRI LUMBAR SPINE WITHOUT CONTRAST": {"cpt": "72148", "wrvu": 1.48},
            "MRI LUMBAR SPINE WITH AND WITHOUT CONTRAST": {"cpt": "72158", "wrvu": 2.29},
            "MRI CERVICAL SPINE WITH AND WITHOUT CONTRAST": {"cpt": "72156", "wrvu": 2.29},
            "MRI CERVICAL SPINE WITHOUT CONTRAST": {"cpt": "72141", "wrvu": 1.48},
            "MRI THORACIC SPINE WITH AND WITHOUT CONTRAST": {"cpt": "72157", "wrvu": 2.29},
            "MRI PELVIS WITHOUT CONTRAST": {"cpt": "72195", "wrvu": 1.46},
            "MRI ANGIOGRAM HEAD WITH AND WITHOUT CONTRAST": {"cpt": "70544", "wrvu": 1.48},
            "MRI HIP WITH AND WITHOUT CONTRAST RIGHT": {"cpt": "73722", "wrvu": 2.29},
            "MRI HIP WITH AND WITHOUT CONTRAST LEFT": {"cpt": "73722", "wrvu": 2.29},
            "MRI BREAST WITH AND WITHOUT CONTRAST BILATERAL": {"cpt": "77059", "wrvu": 2.4},
            "MRI SHOULDER WITH AND WITHOUT CONTRAST LEFT": {"cpt": "73223", "wrvu": 2.29},
            "MRI MRCP WITH AND WITHOUT CONTRAST": {"cpt": "74183", "wrvu": 2.27},
            "MRI ANKLE WITHOUT CONTRAST RIGHT": {"cpt": "73721", "wrvu": 1.48},
            
            # X-ray procedures
            "XR ANKLE MINIMUM 3 VIEWS": {"cpt": "73610", "wrvu": 0.22},
            "XR ANKLE MINIMUM 3 VIEWS RIGHT": {"cpt": "73610", "wrvu": 0.22},
            "XR ANKLE MINIMUM 3 VIEWS LEFT": {"cpt": "73610", "wrvu": 0.22},
            "XR HIP 2 OR 3 VIEWS WITH OR WITHOUT PELVIS": {"cpt": "73521", "wrvu": 0.22},
            "XR HIP 2 OR 3 VIEWS RIGHT WITH OR WITHOUT PELVIS": {"cpt": "73521", "wrvu": 0.22},
            "XR HIP 2 VIEWS BILATERAL WITH OR WITHOUT PELVIS": {"cpt": "73521", "wrvu": 0.22},
            "XR CHEST 1 VIEW": {"cpt": "71045", "wrvu": 0.18},
            "XR CHEST 2 VIEWS": {"cpt": "71046", "wrvu": 0.22},
            "XR ABDOMEN 1 VIEW": {"cpt": "74018", "wrvu": 0.18},
            "XR ABDOMEN 2 VIEWS": {"cpt": "74019", "wrvu": 0.23},
            "XR ABDOMEN 2 VIEWS COMPLETE": {"cpt": "74019", "wrvu": 0.23},
            "XR LUMBAR SPINE 1 VIEW": {"cpt": "72100", "wrvu": 0.22},
            "XR LUMBAR SPINE 2 OR 3 VIEWS": {"cpt": "72100", "wrvu": 0.22},
            "XR LUMBAR SPINE MINIMUM 4 VIEWS": {"cpt": "72100", "wrvu": 0.22},
            "XR CERVICAL SPINE 1 VIEW": {"cpt": "72040", "wrvu": 0.22},
            "XR CERVICAL SPINE FLEXION AND EXTENSION VIEW ONLY": {"cpt": "72040", "wrvu": 0.22},
            "XR C-SPINE 2 OR 3 VIEWS": {"cpt": "72040", "wrvu": 0.22},
            "XR THORACIC SPINE 2 VIEWS": {"cpt": "72070", "wrvu": 0.22},
            "XR SHOULDER MINIMUM 2 VIEWS": {"cpt": "73030", "wrvu": 0.22},
            "XR SHOULDER MINIMUM 2 VIEWS RIGHT": {"cpt": "73030", "wrvu": 0.22},
            "XR SHOULDER MINIMUM 2 VIEWS LEFT": {"cpt": "73030", "wrvu": 0.22},
            "XR KNEE MINIMUM 2 VIEWS": {"cpt": "73560", "wrvu": 0.22},
            "XR KNEE 2 VIEWS LEFT": {"cpt": "73560", "wrvu": 0.22},
            "XR KNEE 2 VIEWS RIGHT": {"cpt": "73560", "wrvu": 0.22},
            "XR KNEE 3 VIEWS RIGHT": {"cpt": "73560", "wrvu": 0.22},
            "XR KNEE MINIMUM 4 VIEWS RIGHT": {"cpt": "73560", "wrvu": 0.22},
            "XR FOOT MINIMUM 3 VIEWS LEFT": {"cpt": "73620", "wrvu": 0.22},
            "XR FOOT MINIMUM 3 VIEWS RIGHT": {"cpt": "73620", "wrvu": 0.22},
            "XR FOOT 2 VIEWS LEFT": {"cpt": "73620", "wrvu": 0.22},
            "XR FOOT 2 VIEWS RIGHT": {"cpt": "73620", "wrvu": 0.22},
            "XR ELBOW MINIMUM 3 VIEWS LEFT": {"cpt": "73070", "wrvu": 0.22},
            "XR ELBOW MINIMUM 3 VIEWS RIGHT": {"cpt": "73070", "wrvu": 0.22},
            "XR ELBOW 2 VIEWS RIGHT": {"cpt": "73070", "wrvu": 0.22},
            "XR ELBOW 2 VIEWS LEFT": {"cpt": "73070", "wrvu": 0.22},
            "XR PELVIS 1 OR 2 VIEWS": {"cpt": "72170", "wrvu": 0.22},
            "XR FACIAL BONES 3 OR MORE VIEWS": {"cpt": "70140", "wrvu": 0.22},
            "XR RIBS UNILAT LEFT AND PA CHEST MIN 3 VIEWS": {"cpt": "71100", "wrvu": 0.22},
            "XR FEMUR 2 OR MORE VIEWS LEFT": {"cpt": "73550", "wrvu": 0.22},
            "XR TOE 1ST LEFT": {"cpt": "73660", "wrvu": 0.22},
            "XR HAND MINIMUM 3 VIEWS RIGHT": {"cpt": "73120", "wrvu": 0.22},
            "XR FOREARM 2 VIEWS RIGHT": {"cpt": "73090", "wrvu": 0.22},
            "XR WRIST MINIMUM 3 VIEWS LEFT": {"cpt": "73110", "wrvu": 0.22},
            "XR WRIST MINIMUM 3 VIEWS RIGHT": {"cpt": "73110", "wrvu": 0.22},
            
            # PET procedures
            "PET CT SKULL BASE TO MID THIGH INIT": {"cpt": "78815", "wrvu": 4.8},
            "PET CT SKULL BASE TO MID THIGH SUBSEQUENT": {"cpt": "78815", "wrvu": 4.8},
            
            # Fluoroscopy procedures
            "FL GUIDANCE VENOUS ACCESS": {"cpt": "77001", "wrvu": 0.25},
            "FL ESOPHAGRAM COMPLETE": {"cpt": "74220", "wrvu": 0.85},
            "FL ESOPHAGRAM SINGLE CONTRAST": {"cpt": "74220", "wrvu": 0.85},
            "FL UPPER GI WITH SMALL BOWEL FOLLOW THROUGH": {"cpt": "74245", "wrvu": 1.25},
            "FL RETROGRADE PYELOGRAM WITH AND WITHOUT KUB": {"cpt": "74420", "wrvu": 1.0},
            "FL SWALLOW STUDY FOR SPEECH": {"cpt": "74230", "wrvu": 0.85},
            "FLUORO GUIDANCE VENOUS ACCESS": {"cpt": "77001", "wrvu": 0.25},
            "FLUORO ESOPHAGRAM COMPLETE": {"cpt": "74220", "wrvu": 0.85},
            "FLUOROSCOPY GUIDED SPINAL INJECTION": {"cpt": "77003", "wrvu": 0.67},
            
            # Nuclear Medicine procedures
            "NM BONE SCAN 3 PHASE": {"cpt": "78320", "wrvu": 0.96},
            "NM LUNG SCAN VENTILATION AND PERFUSION IMAGING": {"cpt": "78588", "wrvu": 1.4},
            "NM LIVER SCAN STATIC ONLY": {"cpt": "78215", "wrvu": 0.74},
            "NM GASTRIC EMPTYING STUDY": {"cpt": "78264", "wrvu": 1.0},
            "NM HIDA SCAN": {"cpt": "78226", "wrvu": 0.96},
            
            # Interventional Radiology procedures
            "IR EMBOLIZATION ARTERIAL": {"cpt": "37204", "wrvu": 3.2},
            "IR KYPHOPLASTY LUMBAR": {"cpt": "22523", "wrvu": 2.8},
            
            # Procedures
            "THORACENTESIS": {"cpt": "32554", "wrvu": 1.2},
            "PARACENTESIS": {"cpt": "49082", "wrvu": 1.0},
            
            # Bone density procedures
            "DXA BONE DENSITY SPINE AND HIP": {"cpt": "77080", "wrvu": 0.17},
            
            # Mammography procedures
            "MAMMO DIGITAL 3D SCREENING BILATERAL": {"cpt": "77067", "wrvu": 0.7},
            "MAMMO DIGITAL 3D DIAGNOSTIC UNILATERAL LEFT": {"cpt": "77066", "wrvu": 0.7},
        }
    
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