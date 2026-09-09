import os
import re
import cohere
import time
import numpy as np
from typing import List
from dotenv import load_dotenv
# from openai import OpenAI


load_dotenv()
class IA_Tools():
    text = ''
    posibilities = []

    @classmethod
    def get_compare_prompt(self):
        return(
            f"Dado el texto de referencia '{self.text}', evalúa cuál de las opciones proporcionadas es la más similar textualmente y léxicamente. "
            f"Sigue estas reglas estrictamente:\n"
            f"- Elimina letras repetidas seguidas en el texto de referencia y en las opciones antes de compararlas. Las repeticiones no agregan valor a la palabra.\n"
            f"- Si el texto se refiere a un nombre propio de una empresa, pero no coincide textualmente con ninguna opción, devuelve un -.\n"
            f"- Devuelve el texto exacto de la opción más parecida considerando tanto similitud textual como léxica.\n"
            f"- Si ninguna opción es suficientemente similar o relevante, responde con una cadena vacía.\n"
            f"- Bajo ninguna circunstancia deben confundirse palabras opuestas o conceptualmente diferentes.\n"
            f"- Tus unicas opciones para responder es un - o la opcion elegida.\n"
            f"Opciones: {', '.join(self.posibilities)}"
        )
    
    @classmethod
    def get_insert_new_text_prompt(self):
        return (
            f"Dado el texto \"{self.text}\", realiza las siguientes acciones y devuelve únicamente el texto corregido, sin explicaciones ni comentarios adicionales:\n"
            f"- Elimina las letras repetidas seguidas que no aporten valor al significado de la palabra final (por ejemplo, 'buuuueno' -> 'bueno').\n"
            f"- Capitaliza las palabras, excepto aquellas que sean stop words del idioma español, a menos que formen parte de un nombre propio de una empresa, ubicación, o persona.\n"
            f"- Completa abreviaturas o palabras cortadas en el texto si es posible identificar su significado, pero ignora las siglas.\n"
            f"Devuelve únicamente el texto final corregido."
        )
    
    @classmethod
    def filter_embeddings(self,list_embeddings:List[List[float]], posibilities:List[str],threshold:float=0.8)->List[List[float]]:
        similitudes = []
        for i in range(len(posibilities)):
            similitudes.append((self.cosino_similarity(list_embeddings[0], list_embeddings[i+1]), posibilities[i]))
        similitudes.sort(key=lambda x: x[0], reverse=True)
        similitudes = [item for item in similitudes if item[0] > threshold]
        
        if len(similitudes) == 0:
            return '-'
        else:
            return similitudes[0][1]

    @staticmethod
    def cosino_similarity(embedding1, embedding2):
        embedding1 = np.array(embedding1)
        embedding2 = np.array(embedding2)

        return np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))
    
    @staticmethod
    def standardize_text(text:str)->str:
        spanish_stop_words = [
                "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las", "por", "un", "para", 
                "con", "no", "una", "su", "al", "lo", "como", "más", "pero", "sus", "le", "ya", "o", "este", 
                "sí", "porque", "esta", "entre", "cuando", "muy", "sin", "sobre", "también", "me", "hasta", 
                "hay", "donde", "quien", "desde", "todo", "nos", "durante", "todos", "uno", "les", "ni", 
                "contra", "otros", "ese", "eso", "ante", "ellos", "e", "esto", "mí", "antes", "algunos", 
                "qué", "unos", "yo", "otro", "otras", "otra", "él", "tanto", "esa", "estos", "mucho", 
                "quienes", "nada", "muchos", "cual", "poco", "ella", "estar", "estas", "algunas", "algo", 
                "nosotros", "mi", "mis", "tú", "te", "ti", "tu", "tus", "ellas", "nosotras", "vosotros", 
                "vosotras", "os", "mío", "mía", "míos", "mías", "tuyo", "tuya", "tuyos", "tuyas", "suyo", 
                "suya", "suyos", "suyas", "nuestro", "nuestra", "nuestros", "nuestras", "vuestro", "vuestra", 
                "vuestros", "vuestras", "esos", "esas", "estoy", "estás", "está", "estamos", "estáis", 
                "están", "esté", "estés", "estemos", "estéis", "estén", "estaré", "estarás", "estará", 
                "estaremos", "estaréis", "estarán", "estaría", "estarías", "estaríamos", "estaríais", 
                "estarían", "estaba", "estabas", "estábamos", "estabais", "estaban", "estuve", "estuviste", 
                "estuvo", "estuvimos", "estuvisteis", "estuvieron", "estuviera", "estuvieras", "estuviéramos", 
                "estuvierais", "estuvieran", "estuviese", "estuvieses", "estuviésemos", "estuvieseis", 
                "estuviesen", "estando", "estado", "estada", "estados", "estadas", "estad", "he", "has", 
                "ha", "hemos", "habéis", "han", "haya", "hayas", "hayamos", "hayáis", "hayan", "habré", 
                "habrás", "habrá", "habremos", "habréis", "habrán", "habría", "habrías", "habríamos", 
                "habríais", "habrían", "había", "habías", "habíamos", "habíais", "habían", "hube", "hubiste", 
                "hubo", "hubimos", "hubisteis", "hubieron", "hubiera", "hubieras", "hubiéramos", "hubierais", 
                "hubieran", "hubiese", "hubieses", "hubiésemos", "hubieseis", "hubiesen", "habiendo", 
                "habido", "habida", "habidos", "habidas", "soy", "eres", "es", "somos", "sois", "son", 
                "sea", "seas", "seamos", "seáis", "sean", "seré", "serás", "será", "seremos", "seréis", 
                "serán", "sería", "serías", "seríamos", "seríais", "serían", "era", "eras", "éramos", 
                "erais", "eran", "fui", "fuiste", "fue", "fuimos", "fuisteis", "fueron", "fuera", "fueras", 
                "fuéramos", "fuerais", "fueran", "fuese", "fueses", "fuésemos", "fueseis", "fuesen", 
                "sintiendo", "sentido", "sentida", "sentidos", "sentidas", "siente", "sentid", "tengo", 
                "tienes", "tiene", "tenemos", "tenéis", "tienen", "tenga", "tengas", "tengamos", "tengáis", 
                "tengan", "tendré", "tendrás", "tendrá", "tendremos", "tendréis", "tendrán", "tendría", 
                "tendrías", "tendríamos", "tendríais", "tendrían", "tenía", "tenías", "teníamos", "teníais", 
                "tenían", "tuve", "tuviste", "tuvo", "tuvimos", "tuvisteis", "tuvieron", "tuviera", 
                "tuvieras", "tuviéramos", "tuvierais", "tuvieran", "tuviese", "tuvieses", "tuviésemos", 
                "tuvieseis", "tuviesen", "teniendo", "tenido", "tenida", "tenidos", "tenidas", "tened"
            ]
        text = str(text)
        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        
        text_list = []
        for word in text.split():
            if word.lower() in spanish_stop_words:
                text_list.append(word.lower())
            elif len(word)<=5 and word.isupper():
                text_list.append(word)
            else:
                text_list.append(word.capitalize())        
        text_list[0] = text_list[0] if len(word)<=5 and word.isupper() else text_list[0].capitalize()
        
        text = [re.sub(r'^\((\w)', lambda m: '(' + m.group(1).upper(),word) if word.startswith('(') else word for word in text_list]
        text = ' '.join(text)

        return text
    
    
# class Datax_OpenAI(IA_Tools):
#     api_key = os.getenv('OPENAI_API_KEY')
#     openai_client = OpenAI(
#         api_key=api_key)
    
#     @classmethod
#     def compare_posibilities(self,text:str, posibilities:List[str], model='gpt-3.5-turbo')->str:
#         self.text = text
#         self.posibilities = posibilities

#         response = self.openai_client.chat.completions.create(
#                 model=model,
#                 messages=[
#                     # {
#                     #     "role": "system",
#                     #     "content": (
#                     #         "Eres un asistente experto en evaluación de similitudes. "
#                     #         "Tus unicas opciones para responder es o una cadena vacia o una opcion de las mostradas. "
#                     #         "Devuelve la opción completa más similar de la lista proporcionada, "
#                     #         "tal como aparece en la lista. Si ninguna coincide adecuadamente, responde con una cadena vacía."
#                     #     ),
#                     # },
#                     {"role": "user", "content": self.get_compare_prompt()},
#                 ],
#                 # max_tokens=50,  # Incrementado para manejar opciones más largas
#                 temperature=0.7,
#             )
#         gpt_response = response.choices[0].message.content
#         print('TEXTO', text)
#         print(f'OPCIONES: {posibilities}')
#         print("RESPUESTA",gpt_response)        
#         return gpt_response
        
#     @classmethod
#     def insert_new_text(self,text:str, model='gpt-4')->str:
#         self.text = text
#         print(f'NEW TEXT:{text}')        
    
#         response = self.openai_client.chat.completions.create(
#                 model=model,
#                 messages=[                    
#                     {"role": "user", "content": self.get_insert_new_text_prompt()},
#                 ],
#                 temperature=0.2,
#             )
    
#         ai_response = response.choices[0].message.content        
#         return ai_response

class Datax_Cohere(IA_Tools):
    _cohere_client = None

    @classmethod
    def _get_client(cls):
        if cls._cohere_client is None:
            api_key = os.getenv('COHERE_API_KEY')
            cls._cohere_client = cohere.ClientV2(api_key=api_key)
        return cls._cohere_client

    @classmethod
    def compare_posibilities(self, text: str, posibilities: List[str], model='command-a-03-2025') -> str:
        self.text = text
        self.posibilities = posibilities

        try:
            response = self._get_client().chat(
                model=model,
                messages=[{"role": "user", "content": self.get_compare_prompt()}],
                temperature=0.7
            )
            cohere_response = response.message.content[0].text
            print('TEXTO', text)
            print(f'OPCIONES: {posibilities}')
            print("RESPUESTA", cohere_response)
            time.sleep(2)
            return cohere_response
        except Exception as e:
            print(f"Warning: Cohere compare_posibilities error: {e}")
            return '-'
    
    @classmethod
    def compare_posibilities_embeddings(self,text:str, posibilities:List[str], model='embed-multilingual-v3.0')->str:
        try:
            threshold = 0.9 if (text.isupper() and len(text)<=5) else 0.8
            print('TEXTO', text)
            print(f'OPCIONES: {posibilities}')
            text = text.lower()
            lower_posibilities = [posibility.lower() for posibility in posibilities]

            response = self._get_client().embed(
                texts= [text] + lower_posibilities,
                model=model,
                input_type='search_query',  # para comparación de textos/palabras
                embedding_types=['float']
            )

            embeddings = response.embeddings.float_

            embeddings_response = self.filter_embeddings(embeddings, posibilities, threshold=threshold)

            print("RESPUESTA",embeddings_response)
            return embeddings_response
        except Exception as e:
            print("There is an error trying to compare posibilities")
            time.sleep(6)
            return '-'
    
    @classmethod
    def insert_new_text(self, text: str, model='command-a-03-2025') -> str:
        self.text = text
        print(f'NEW TEXT:{text}')        

        try:
            response = self._get_client().chat(
                model=model,
                messages=[{"role": "user", "content": self.get_insert_new_text_prompt()}],
                temperature=0.2
            )        
            if response and response.message and response.message.content:
                return response.message.content[0].text
        except Exception as e:
            print(f"Warning: Cohere insert_new_text API error: {e}")
        
        return self.standardize_text(text=text)