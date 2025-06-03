import re
magnitude_factors = {
    "miles": 1_000,
    "millones": 1_000_000,
    "billones": 1_000_000_000,
    "trillones": 1_000_000_000_000
}
iso4217_currencies = {
    "dolar": "USD",
    "us$": "USD",
    "boliviano": "BOB",
}
iso4217_currencies_exchange_rate = {    
    "argentina peso": "ARS",
    "australia dolar": "AUD",
    "brasil real": "BRL",
    "canada dolar": "CAD",
    "chile peso": "CLP",
    "china yuan": "CNY",
    "colombia peso": "COP",
    "corea sur won": "KRW",
    "dinamarca corona": "DKK",
    "ecuador dolar": "USD",
    "euro": "EUR",
    "hong kong dolar": "HKD",
    "india rupia": "INR",
    "reino unido libra": "GBP",
    "japon yen": "JPY",
    "mexico peso": "MXN",
    "noruega corona": "NOK",
    "paraguay guarani": "PYG",
    "peru sol": "PEN",
    "rusia rublo": "RUB",
    "singapur dolar": "SGD",
    "suecia corona": "SEK",
    "suiza franco": "CHF",
    "tailandia baht": "THB",
    "taiwan dolar": "TWD",
    "bolivia unidad": "UFV",
    "uruguay peso": "UYU",
    "estados unidos": "USD",
    "venezuela bolivar": "VED",
    "us$": "USD",
}

def formated_col(col:str):
    col = re.sub(r'\s+',' ',str(col).lower().strip())
    return re.sub(r'\s','_',col)

unit_abbreviations = {
    "libra": "lb",
    "troy": "oz t",
    "barril": "bbl"
}