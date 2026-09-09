import os
import traceback
import requests
import pandas as pd
from datetime import datetime

from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import format_date


class D_BO_000000250(Download_Base):

    def check_new_data(self, main_url, updated_to, path, key_words, format='%Y-%m-%d'):
        """
        Extracts data from the main_url dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            path (str): The directory path to store temporary files.
            key_words (str): A string used to name the Excel file.
            format (str): The format of the dates. Default is '%Y-%m-%d'.

        Returns:
            list: A list of dictionaries containing information about the extracted data.
        """
        updated_to = format_date(updated_to)
        today = datetime.today()

        try:
            print(f"Checking data for {main_url} ...")

            if updated_to.date() >= today.date():
                print(f"There is no new data after: {updated_to.strftime(format)}")
                return []

            url = "https://senamhi.gob.bo/pronjsondiario.php?dias=1"
            daily_forecast_url = "https://senamhi.gob.bo/pronosticoJson.php"
            new_order = [
                'Departamento', 'Estacion', 'Fecha', 'Estado_Cielo',
                'Temperatura [°C]', 'Precipitación [mm]',
                'Humedad_Relativa [%]', 'Velocidad_Viento [Km/h]'
            ]

            headers = getattr(self, 'headers', {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })

            weather_stations_response = requests.get(url, timeout=15, headers=headers)
            if 200 <= weather_stations_response.status_code < 300:
                weather_stations = weather_stations_response.json()
            else:
                raise Exception(f"Weather stations without response: status {weather_stations_response.status_code}")

            station_dataframes = []
            for station in weather_stations:
                try:
                    daily_forecast_response = requests.get(
                        daily_forecast_url,
                        timeout=15,
                        headers=headers,
                        params={"ciudad": station.get("estacion", "")}
                    )

                    if 200 <= daily_forecast_response.status_code < 300:
                        daily_forecast = daily_forecast_response.json()
                        daily_forecast = {key: value for d in daily_forecast for key, value in d.items()}
                        df = pd.DataFrame({
                            "Fecha": daily_forecast.get("Fecha"),
                            "Estado_Cielo": daily_forecast.get("Fenomeno"),
                            "Temperatura [°C]": daily_forecast.get("Temperatura"),
                            "Precipitación [mm]": daily_forecast.get("Precipitación"),
                            "Humedad_Relativa [%]": daily_forecast.get("Humedad Relativa"),
                            "Velocidad_Viento [Km/h]": daily_forecast.get("Vientos"),
                        })
                        if not df.empty:
                            df["Departamento"] = station.get("departamento", "")
                            df["Estacion"] = station.get("estacion", "")
                            available_cols = [c for c in new_order if c in df.columns]
                            df = df[available_cols]
                            station_dataframes.append(df)
                        else:
                            print(f"Station without data: {station.get('estacion')}")
                    else:
                        print(f"Url station broken: {station.get('estacion')}")
                except Exception as ex_st:
                    print(f"Error fetching station {station.get('estacion')}: {ex_st}")
                    continue

            if not station_dataframes:
                print("No station dataframes could be built.")
                return []

            daily_forecast_df = pd.concat(station_dataframes, axis=0)
            os.makedirs(path, exist_ok=True)
            file_path = os.path.join(path, f"{today.strftime(format)}_{key_words}.xlsx")
            daily_forecast_df.to_excel(file_path, index=False)
            print(f"Data was extracted and saved to: {file_path}")

            return [{
                "tmp_path": file_path,
                "updated_to": today.strftime(format=format),
                "download_url": '-',
            }]

        except Exception as e:
            print(f"An error occurred: {e}")
            traceback.print_exc()
            return []


# Compatibility alias
Executor_D_BO_000000250 = D_BO_000000250
