import sys, re, traceback, requests, os
sys.path.append("..")
from datetime import datetime
import pandas as pd
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number, last_day_month,text_extract
from models.download.Download_Base import Download_Base

class D_BO_000000250(Download_Base):

    def check_new_data(self, main_url, updated_to,path,key_words, format='%Y-%m-%d'):
        """
        Extracts data from the main_url dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            path (str): The directory path to store temporary files.
            key_words (str): A string used to name the CSV file.
            format (str): The format of the dates. Default is '%Y-%m-%d'.

        Returns:
            list: A list of dictionaries containing information about the extracted data.
        """
        # Convert updated_to string to datetime object
        updated_to = format_date(updated_to)
        today = datetime.today()

        try:
            # Launch browser and navigate to main URL
            print(f"Launching browser and navigating to {main_url} ...")
            
            if updated_to >= today:
                print(f"There is no new data after: {updated_to.strftime(format)}")
                return []
            url = f"https://senamhi.gob.bo/pronjsondiario.php?dias=1"
            daily_forecast_url = "https://senamhi.gob.bo/pronosticoJson.php"
            new_order = ['Departamento', 'Estacion','Fecha', 'Estado_Cielo', 'Temperatura [°C]', 'Precipitación [mm]',
            'Humedad_Relativa [%]', 'Velocidad_Viento [Km/h]']

            weather_stations_response = requests.get(url, timeout=10, headers=super().headers)
            if 200 <= weather_stations_response.status_code < 300:
                weather_stations = weather_stations_response.json()
            else: 
                raise Exception("Weather stations without response")
            station_dataframes = []
            for station in weather_stations:
                
                daily_forecast_response = requests.get(daily_forecast_url, timeout=10, headers=super().headers, params={"ciudad":station["estacion"]})

                if 200 <= daily_forecast_response.status_code < 300:
                    daily_forecast = daily_forecast_response.json()
                    daily_forecast = {key: value for d in daily_forecast for key, value in d.items()}
                    df = pd.DataFrame({
                        "Fecha": daily_forecast["Fecha"],
                        "Estado_Cielo": daily_forecast["Fenomeno"],
                        "Temperatura [°C]": daily_forecast["Temperatura"],
                        "Precipitación [mm]": daily_forecast["Precipitación"],
                        "Humedad_Relativa [%]": daily_forecast["Humedad Relativa"],
                        "Velocidad_Viento [Km/h]": daily_forecast["Vientos"],
                    })
                    if not df.empty:
                        df["Departamento"] = station["departamento"]
                        df["Estacion"] = station["estacion"]
                        df = df[new_order]
                        station_dataframes.append(df)
                    else:
                        print(f"Station without data: {station['estacion']}")
                        continue
                else: 
                    print(f"Url station broken: {station['estacion']}")
            
            daily_forecast_df = pd.concat(station_dataframes,axis=0)
            file_path = os.path.join(path,f"{today.strftime(format)}_{key_words}.xlsx")
            daily_forecast_df.to_excel(file_path,index=False,)
            print("Data was extracted.")

            # Return information about the extracted data
            return [{
                "tmp_path":file_path,
                "updated_to":today.strftime(format=format),
                "download_url":'-',
            }]

        except Exception as e:
            print(f"An error ocurred: {e}")
            traceback.print_exc()
            return []
    

# if __name__ == "__main__":
#     robot = D_BO_000000250()
#     x = robot.check_new_data(main_url="http://senamhi.gob.bo/index.php/pcpn",updated_to="2023-5-21",path = r'D:\DATAX\Download_SPIM\base_path\tmp', key_words="precipitacion diaria")
#     print(len(x))
#     print(x)
#     # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r'\\10.0.0.9\SPIM\APS\Pensiones-Estad.Mensuales\02-Fondo de Ahorro Previsional\04-Patrimonio del FAP\01-Inversiones de FCC, RP, RC, MVV y FSOL en el FAP\tmp\2024-05-23_161619Febrero.pdf'}]
#     # y = robot.compare_files(files_paths=files,updated_to="2023-01-21")
#     # print(y)

Executor_D_BO_000000250 = D_BO_000000250
Robot = D_BO_000000250
