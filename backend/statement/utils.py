import pandas as pd

def load_csv(file_path):
    try:
        df = pd.read_csv(file_path, sep=';')
    except pd.errors.ParserError:
        df = pd.read_csv(file_path, sep=',')
    return df