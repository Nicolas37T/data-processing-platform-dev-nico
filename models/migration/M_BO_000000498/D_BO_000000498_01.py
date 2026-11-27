import numpy as np
import pandas as pd
from rapidfuzz import process, fuzz
from models.conversion.tools.ia_tools import IA_Tools
from models.migration.Migration_Base import Migration_Base
from models.migration.tools.migration_tools import iso4217_currencies_exchange_rate

class D_BO_000000498_01(Migration_Base):    

    def standard_report(self,dataframe:pd.DataFrame, conversion_factor:int):        
        metric_unit = np.where(dataframe['nv1'].str.contains(r'usd\s+per\s+unit',regex=True,case=False),'USD',dataframe['currency'])

        dataframe.insert(len(dataframe.columns)-1,column='metrica',value='moneda')
        dataframe.insert(len(dataframe.columns)-1,column='unidad_metrica',value=metric_unit)        
        
        return ({
            "conversion_factor": 1
        },dataframe)