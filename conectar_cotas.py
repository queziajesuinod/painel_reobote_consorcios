import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import os

SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), 'client.json')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def conectar_cotas():
    credentials = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)

    SPREADSHEET_ID = '1luLlcE7iDl4l6EiSGHI_3lAs8lutqy7Hra1iBdBvdZk'
    RANGE_NAME = 'Cotas!A1:I'

    service = build('sheets', 'v4', credentials=credentials)
    sheet = service.spreadsheets()

    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
    values = result.get('values', [])

    if not values:
        return pd.DataFrame()

    cotas = pd.DataFrame(values[1:], columns=values[0])

    cotas['ANO'] = cotas['MÊS'].apply(lambda x: int(x.split('-')[-1]) if '-' in x else 0)
    cotas['VALOR TOTAL'] = cotas['VALOR TOTAL'].apply(
        lambda x: float(x.replace('R$', '').replace('.', '').replace(',', '.').strip()) if isinstance(x, str) else 0.0
    )

    return cotas
