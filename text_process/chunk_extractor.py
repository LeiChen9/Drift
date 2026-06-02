import json
import os
from pathlib import Path
import pdb

def load_json(filepath):
    """Load JSON file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_text_from_tree(book_tree, start_anchor, end_anchor):
    """
    Recursively search through book_tree to find and extract text between anchors.
    Returns the concatenated text between start and end sentence anchors.
    """
    all_paragraphs = []
    
    def collect_paragraphs(node):
        """Recursively collect all paragraphs from tree structure"""
        if isinstance(node, dict):
            if "paragraphs" in node:
                all_paragraphs.extend(node["paragraphs"])
            if "children" in node:
                for child in node["children"].values():
                    collect_paragraphs(child)
        elif isinstance(node, list):
            for item in node:
                collect_paragraphs(item)
    
    # Collect all paragraphs in order
    for chapter in book_tree.values():
        collect_paragraphs(chapter)
    
    # Find start and end indices
    start_idx = None
    end_idx = None
    
    for i, para in enumerate(all_paragraphs):
        if start_anchor in para:
            start_idx = i
        if end_anchor in para:
            end_idx = i
            break
    
    if start_idx is not None and end_idx is not None:
        return '\n'.join(all_paragraphs[start_idx:end_idx+1])
    
    return None

def extract_chunks(book_data_path, outline_path, output_path=None):
    """
    Extract chunks from book based on outline anchors.
    
    Args:
        book_data_path: Path to reason_op.json
        outline_path: Path to ep1/outline.json
        output_path: Optional path to save output JSON
    
    Returns:
        Dictionary with chunk_id as key and extracted text as value
    """
    # Load data
    book_data = load_json(book_data_path)
    outline_data = load_json(outline_path)
    
    chunks_output = {}
    
    # Extract each chunk
    for chunk in outline_data.get('chunks', []):
        chunk_id = chunk['chunk_id']
        start_anchor = chunk['start_sentence_anchor']
        end_anchor = chunk['end_sentence_anchor']
        
        # Extract text from book tree
        extracted_text = extract_text_from_tree(
            book_data.get('book_tree', {}),
            start_anchor,
            end_anchor
        )
        
        if extracted_text:
            chunks_output[chunk_id] = extracted_text
        else:
            print(f"Warning: Could not extract text for {chunk_id}")
            pdb.set_trace()
    
    # Save output if path provided
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(chunks_output, f, ensure_ascii=False, indent=2)
        print(f"Output saved to {output_path}")
    
    return chunks_output

if __name__ == "__main__":
    base_path = Path(__file__).parent.parent
    book_data_path = base_path / "asset" / "reason_op.json"
    outline_path = base_path / "asset" / "reason_op" / "ep1" / "outline.json"
    output_path = base_path / "output" / "chunks.json"
    
    result = extract_chunks(str(book_data_path), str(outline_path), str(output_path))
    import pdb; pdb.set_trace()
    print(f"Extracted {len(result)} chunks")