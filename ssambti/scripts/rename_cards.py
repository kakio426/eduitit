import os

# Map from MBTI to Animal Name
MBTI_ANIMAL_MAP = {
    'ISTJ': 'penguin',
    'ISFJ': 'quokka',
    'INFJ': 'snow_leopard',
    'INTJ': 'black_cat',
    'ISTP': 'raccoon',
    'ISFP': 'koala',
    'INFP': 'sea_otter',
    'INTP': 'owl',
    'ESTP': 'cheetah',
    'ESFP': 'dolphin',
    'ENFP': 'red_panda',
    'ENTP': 'meerkat',
    'ESTJ': 'tiger',
    'ESFJ': 'elephant',
    'ENFJ': 'golden_retriever',
    'ENTJ': 'lion',
}

base_dir = r'c:\Users\kakio\eduitit\static\ssambti\images\share_cards'

for mbti, animal in MBTI_ANIMAL_MAP.items():
    old_name = os.path.join(base_dir, f'{mbti}_card.png')
    new_name = os.path.join(base_dir, f'{animal}_card.png')
    
    if os.path.exists(old_name):
        try:
            os.rename(old_name, new_name)
            print(f'Renamed: {mbti}_card.png -> {animal}_card.png')
        except Exception as e:
            print(f'Error renaming {old_name}: {e}')
    else:
        print(f'File not found: {old_name}')
