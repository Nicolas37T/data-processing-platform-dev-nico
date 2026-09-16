from models.download.Download_Base import Download_Base
import sys
sys.path.append("..")
from models.download.SNIS import SNIS

class D_BO_000000213(SNIS):

    def get_data(self, main_url,path, updated_to,format='%Y-%m-%d'):
        """
        Extracts data from URLs for files dated in the present year.

        Parameters:
            main_url (str): The URL of the main page.
            path (str): The path where files are stored.
            updated_to (str): The latest date for which the database contains records.
            format (str): The date format to use for the 'updated_to' field.

        Returns:
            str: A temporary path where the files were stored or an empty string if there are no files downloaded.
        """
        filters_order=['subsector', 'ambito', 'red_de_salud', 'codmuni','establecimiento', 'nivel', 'tipo', 'institucion', 'municipio', 'provincia', 'semana','mes']
        # Variable information
        variable={
            "code":"03",
            "key_words":"ingresos egresos"
            }
        form_code='304'
        # Call the superclass method to get the temporary path where the files were downloaded
        return super().verify_download(main_url=main_url, path=path,filters_order=filters_order,variable=variable,form_code=form_code)

# if __name__ == "__main__":
#     robot = D_BO_000000213()
#     x = robot.get_data(main_url="https://estadisticas.minsalud.gob.bo/Reportes_Dinamicos/Menu_rep_dinamicos.aspx",updated_to="2024-12-21",path=r"\\10.0.0.9\spim\SNIS\Produccion de Servicios 2\03 Ingresos y Egresos por Servicio de Internacion")
#     print(x)
#     # y = robot.compare_files(file_path=r"\\10.0.0.9\spim\SNIS\Vigilancia Epidemiologica\05 Tuberculosis y Lepra\2022\or_tuberculosis lepra.xls", year=2022)
#     # print(y)

Executor_D_BO_000000213 = D_BO_000000213
Robot = D_BO_000000213
