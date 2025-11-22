from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import random
import io
import base64
import zipfile

app = Flask(__name__)
CORS(app)  # Frontend থেকে রিকোয়েস্ট আসার পারমিশন

def decode_image(data_url):
    """Base64 string থেকে ইমেজ বাইনারি ডেটায় কনভার্ট করে"""
    if not data_url:
        return None
    header, encoded = data_url.split(",", 1)
    return io.BytesIO(base64.b64decode(encoded))

def create_set_document(set_data, set_name):
    doc = Document()
    
    # Title
    heading = doc.add_heading(f'{set_name}', 0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Questions
    for q in set_data['questions']:
        # Question Text
        p = doc.add_paragraph()
        p.add_run(f"{q['questionNumber']}. {q['questionText']}").bold = True
        
        # Question Image (if exists)
        if q.get('questionImage'):
            image_stream = decode_image(q['questionImage'])
            if image_stream:
                try:
                    doc.add_picture(image_stream, width=Inches(3.0))
                except:
                    pass # ইমেজ এরর হলে স্কিপ করবে

        # Options
        for opt in q['options']:
            p_opt = doc.add_paragraph(style='List Bullet')
            p_opt.add_run(f"{opt['letter']}) {opt['text']}")
            
            # Option Image
            if opt.get('image'):
                opt_img_stream = decode_image(opt['image'])
                if opt_img_stream:
                    try:
                        doc.add_picture(opt_img_stream, width=Inches(1.5))
                    except:
                        pass
        
        doc.add_paragraph() # Space between questions

    # Answer Key (New Page)
    doc.add_page_break()
    doc.add_heading(f'Answer Key - {set_name}', level=1)
    
    table = doc.add_table(rows=1, cols=2)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Question No'
    hdr_cells[1].text = 'Correct Option'

    for q in set_data['questions']:
        row_cells = table.add_row().cells
        row_cells[0].text = str(q['questionNumber'])
        row_cells[1].text = str(q['correctAnswer'])

    # Save to memory
    f = io.BytesIO()
    doc.save(f)
    f.seek(0)
    return f

@app.route('/generate-sets', methods=['POST'])
def generate_sets():
    try:
        data = request.json
        questions = data.get('questions')
        num_sets = data.get('numSets')
        
        memory_file = io.BytesIO()
        
        # Create a ZIP file in memory
        with zipfile.ZipFile(memory_file, 'w') as zf:
            
            for i in range(num_sets):
                set_name = f"Set {chr(65 + i)}" # Set A, Set B...
                
                # --- Shuffling Logic ---
                # 1. Shuffle Questions
                shuffled_qs = random.sample(questions, len(questions))
                
                processed_questions = []
                for idx, q in enumerate(shuffled_qs):
                    # 2. Shuffle Options
                    original_options = q['options']
                    # Track correct answer ID before shuffle
                    correct_opt_id = original_options[q['correctAnswer']-1]['id']
                    
                    shuffled_opts = random.sample(original_options, len(original_options))
                    
                    # Find new correct answer index
                    new_correct_idx = -1
                    formatted_opts = []
                    
                    for opt_idx, opt in enumerate(shuffled_opts):
                        if opt['id'] == correct_opt_id:
                            new_correct_idx = opt_idx
                        
                        formatted_opts.append({
                            'letter': chr(97 + opt_idx), # a, b, c, d
                            'text': opt['text'],
                            'image': opt['image']
                        })
                    
                    processed_questions.append({
                        'questionNumber': idx + 1,
                        'questionText': q['questionText'],
                        'questionImage': q['questionImage'],
                        'options': formatted_opts,
                        'correctAnswer': chr(97 + new_correct_idx) # Convert index to letter
                    })

                set_data = {
                    'setName': set_name,
                    'questions': processed_questions
                }
                
                # Generate Word Doc for this set
                docx_file = create_set_document(set_data, set_name)
                
                # Add to ZIP
                zf.writestr(f"{set_name}.docx", docx_file.getvalue())

        memory_file.seek(0)
        
        return send_file(
            memory_file,
            download_name='mcq_sets.zip',
            as_attachment=True,
            mimetype='application/zip'
        )

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)