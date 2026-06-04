import re
import json 
import pdb
def remove_citations(text):
    # 去除正文中的引用标记 [1]、[2] 等
    text = re.sub(r'\s*\[\s*[\d,\s]+\s*\]\s*', ' ', text)
    
    # 去除可能的多个连续空格
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def remove_references(text_list):
    # 去除"参考文献"或"References"之后的所有内容
    return [x for x in text_list if not x.startswith('[ ')]

if __name__ == '__main__':
    with open("../asset/reason_op.json") as f:
        book_data = json.load(f)
    book_text = {}
    for chap_key, chap_content in book_data['book_tree'].items():
        if chap_key == '版权信息':
            continue 
        chap_number, chap_title = chap_key.split(' ')
        chap_body = ''.join(remove_references(chap_content['paragraphs']))
        chap_body = remove_citations(chap_body)
        book_text[chap_number] = {
            'title': chap_title,
            'body': chap_body
        }
    with open("../asset/reason_op_clean.json", 'w', encoding='utf-8') as f:
        json.dump(book_text, f, indent=2, ensure_ascii=False)