from models.download.Download_Base import Download_Base
import sys
sys.path.append("..")
from models.download.Tipo_Cambio import Tipo_Cambio

class D_BO_000000248(Tipo_Cambio):

    def verify_download(self, main_url, updated_to, path):
        """
        Verifies and downloads files dated after the specified update date, and saves them to a temporary path.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            path (str): The directory path where the downloaded files will be saved.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """
        # Call the superclass method to get a list of temporary path files
        return super().verify_download_main(main_url=main_url,updated_to=updated_to,path=path,key_words="rusia")

# if __name__ == "__main__":
#     robot = D_BO_000000248()
#     x = robot.verify_download(main_url="https://estadisticas.minsalud.gob.bo/Reportes_Dinamicos/Menu_rep_dinamicos.aspx",updated_to="2022-12-21",path=r"\\10.0.0.9\spim\SNIS\Produccion de Servicios\08 Micronutrientes")
#     print(x)
#     # y = robot.compare_files(file_path=r"\\10.0.0.9\spim\SNIS\Vigilancia Epidemiologica\05 Tuberculosis y Lepra\2022\or_tuberculosis lepra.xls", year=2022)
#     # print(y)

Executor_D_BO_000000248 = D_BO_000000248
Robot = D_BO_000000248
