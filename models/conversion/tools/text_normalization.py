import re
import unicodedata
import pandas as pd
from rapidfuzz import process, fuzz
from typing import Tuple,Dict,List
from models.conversion.tools.ia_tools import Datax_Cohere

class Text_Normalization():    

    @classmethod
    def get_replaces(self,strings_list:pd.Series, replaces_df:pd.DataFrame,first_execution=False) -> Tuple[Dict[str,str], pd.DataFrame]:
        """
        Identifies and suggests replacements for strings in the given series by comparing them 
        with a reference DataFrame using fuzzy matching techniques.

        Parameters:
        ----------
        strings_list : pd.Series
            A pandas Series containing the strings that need to be processed for possible replacements.
            
        replaces_df : pd.DataFrame
            A DataFrame containing known replacement mappings. Expected columns include:
            - 'srch_value': The normalized search value.
            - 'final_value': The replacement for the corresponding 'srch_value'.

        first_execution : bool, optional
            A flag to indicate whether this is the first execution of the function. This can influence
            how new text entries are handled (default is False).

        Returns:
        -------
        Tuple[Dict[str, str], pd.DataFrame]
            - A dictionary mapping original strings to their corresponding replacements.
            - A DataFrame containing updated and new replacement entries with the columns:
                'original_value', 'srch_value', and 'final_value'.
        """
        # Convert the input series to a DataFrame and standardize the column name to 'string'        
        strings_df = pd.DataFrame(strings_list)
        strings_df = strings_df.rename(columns={
            strings_df.columns[0]: 'string'
        })

        # Normalize the text for comparison
        strings_df['lower_text'] = strings_df['string'].astype(str).apply(lambda x: self.get_srch_value(text=x))
        
        new_replacements_df = pd.DataFrame()

        if replaces_df.empty:
            # If no existing replacements, all strings are considered new
            new_text_df = strings_df.loc[:,['string','lower_text']]            
        else:
            # Perform fuzzy matching between input strings and existing replacements
            strings_df["possible_replacements"] = strings_df['lower_text'].apply(lambda x: process.extract(x, replaces_df['srch_value'],scorer=fuzz.ratio, limit=5))
            
            # Filter the possible replacements based on matching thresholds
            strings_df["possible_replacements"] = strings_df["possible_replacements"].apply(lambda x: self.filter_possible_replacements(list_posiblilities=x))            

            # Identify strings needing further review (multiple possible replacements)
            consult_ia_mask = strings_df['possible_replacements'].apply(lambda x: len(x)>1)
            
            # Replace indices with actual values from replaces_df for easier interpretation
            strings_df['possible_replacements'] = strings_df['possible_replacements'].apply(lambda x: [replaces_df.loc[index,'final_value'] for index in x if index!=None])            
            
            if not strings_df[consult_ia_mask].empty:
                # For ambiguous matches, manually compare possibilities
                strings_df.loc[consult_ia_mask, 'possible_replacements'] = strings_df.loc[consult_ia_mask].apply(lambda x: self.compare_posibilities(text=x['string'], posibilities=x['possible_replacements']),axis=1)

                # Prepare DataFrame for new replacements to be added
                new_replacements_df = strings_df.loc[consult_ia_mask,['string','lower_text','possible_replacements']]
                new_replacements_df = new_replacements_df[new_replacements_df['possible_replacements'].apply(lambda x: x[0]!='')]
                print('NEW REPLACEMENTS',new_replacements_df)

                # Select the first replacement and standardize column names
                new_replacements_df['possible_replacements'] = new_replacements_df['possible_replacements'].apply(lambda x: x[0])
                new_replacements_df = new_replacements_df.rename(columns={
                    'possible_replacements':'final_value',                     
                })
                new_replacements_df = new_replacements_df[['string','lower_text','final_value']]

            # Identify new texts with no possible replacements
            new_text_mask = strings_df['possible_replacements'].apply(lambda x: True if len(x)==0 else (x[0] == ''))
            new_text_df = strings_df.loc[new_text_mask,['string','lower_text']]
            print("NEW TEXT",new_text_df)
        
        # Remove duplicates based on normalized text
        new_text_df = new_text_df.drop_duplicates(subset='lower_text')

        # Insert new text entries if they don't exist in the replacements DataFrame
        new_text_df['final_value'] = new_text_df['string'].apply(lambda x: self.insert_new_text(text=x,first_execution=first_execution))

        # Merge final replacements back into the original DataFrame
        strings_df = strings_df.merge(right=new_text_df[['lower_text','final_value']],how='left',on='lower_text',)

        # For unmatched strings, fill in replacements from possible matches
        final_value_empty_mask = strings_df['final_value'].isna()        
        if not strings_df[final_value_empty_mask].empty:
            strings_df.loc[final_value_empty_mask,'final_value'] = strings_df.loc[final_value_empty_mask,'possible_replacements'].apply(lambda x: x[0])

        # Remove entries where no changes were made (original equals final value)
        equal_mask = strings_df['final_value'] == strings_df['string']
        strings_df = strings_df.loc[~equal_mask,['string','final_value']]
        
        # Convert final DataFrame to dictionary format for easy reference
        replaces_dict = strings_df.set_index('string')['final_value'].to_dict()

        # Combine new text entries with new replacements
        new_text_df = new_text_df[['string','lower_text','final_value']]
        if not new_replacements_df.empty:
            new_text_df = pd.concat([new_text_df,new_replacements_df])
        
        # Remove duplicate entries and rename columns for the final DataFrame
        new_text_df = new_text_df.drop_duplicates(subset='lower_text')
        new_text_df = new_text_df.rename(columns={            
            'string':'original_value',
            'lower_text':'srch_value' 
        })
        
        return (replaces_dict,new_text_df)        
    
    @staticmethod
    def filter_possible_replacements(list_posiblilities:List[Tuple]):
        """
        Filters possible replacements based on predefined match percentage thresholds.

        Parameters:
        ----------
        list_possibilities : List[Tuple]
            A list of tuples where each tuple represents a possible replacement.
            Each tuple should follow the format: (original_value, match_percentage, replacement_value).

        Returns:
        -------
        List
            - If the list is empty, returns an empty list.
            - If the best match exceeds the REPLACEMENT_PERCENTAGE threshold, returns a list with that replacement.
            - If other matches exceed the CONSULT_IA_PERCENTAGE threshold, returns those replacements.
            - If only one replacement is found, appends None to the list for further consideration.
        """
        REPLACEMENT_PERCENTAGE = 90 # Threshold for automatic replacement
        CONSULT_IA_PERCENTAGE = 40 # Threshold for considering potential replacements
        
        if not list_posiblilities:
            # Return an empty list if no possibilities are provided
            return []
        
        best_match = list_posiblilities[0] # Assume the first item is the best match

        if best_match[1] > REPLACEMENT_PERCENTAGE:
            # If the best match percentage exceeds the threshold, return it directly
            return [best_match[2]]
        
        # Filter possibilities that exceed the CONSULT_IA_PERCENTAGE threshold
        posiblilities = [item[2] for item in list_posiblilities if item[1]>CONSULT_IA_PERCENTAGE]
        
        if len(posiblilities) == 1:
            # If only one possibility is found, append None to prompt further review
            posiblilities.append(None)
        return posiblilities
    
    @staticmethod
    def get_srch_value(text:str)->str:
        """
        Normalize and clean a string to create a standardized search value.

        This function performs the following steps:
        1. Removes accents and diacritics from characters.
        2. Converts non-ASCII characters to their closest ASCII equivalents.
        3. Removes all non-alphanumeric characters except for periods.
        4. Converts the string to lowercase for case-insensitive comparison.

        Args:
            text (str): The input string to be normalized and cleaned.

        Returns:
            str: The processed string suitable for consistent search operations.
        """
        # Normalize text to separate accents from characters and encode to ASCII, ignoring non-ASCII characters
        srch_text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')

        # Remove all non-alphanumeric characters except periods, and eliminate spaces
        srch_text = re.sub(r'[^a-zA-Z0-9\.]|\s+', '', srch_text).lower()

        return srch_text
    
    @staticmethod
    def insert_new_text(text:str,first_execution=False)->str:
        """
        Process and standardize text based on execution context.

        This function either inserts new AI-processed text or standardizes it, 
        depending on whether it is the first execution.

        Args:
            text (str): The input text to be processed.
            first_execution (bool, optional): Flag indicating if this is the first 
            execution. Defaults to False.

        Returns:
            str: The processed or standardized text.
        """
        if not first_execution:
            # If not the first execution, generate new text using AI processing
            ai_response = Datax_Cohere.insert_new_text(text=text)

            # Remove single and double quotes from AI response
            ai_response = re.sub(r'[\'\"]','',ai_response.strip())

            # Replace multiple spaces with a single space
            text = re.sub(r'\s+',' ',ai_response)
        else:
            # If first execution, standardize the input text
            text = Datax_Cohere.standardize_text(text=text)
        return text
    
    @staticmethod
    def compare_posibilities(text:str, posibilities:List[str]):
        """
        Compare a given text with a list of possibilities using AI 
        and return the best match.
        T

        Args:
            text (str): The input text to compare.
            posibilities (List[str]): A list of possible matching strings.

        Returns:
            List[str]: A list containing the best match. If no match is found, 
            an empty string is returned.
        """
        # Use AI to compare the text against possible matches
        response = Datax_Cohere.compare_posibilities_embeddings(text=text, posibilities=posibilities)
        
        # Remove single and double quotes from the AI response
        response = re.sub(r'[\'\"]','',response)

        # If the AI response is '-', return an empty string to indicate no match
        response = '' if response == '-' else response
        return [response]
    
    @staticmethod
    def standarize_dataframe_cols(dataframe:pd.DataFrame)->pd.DataFrame:
        old_cols = dataframe.columns
        old_cols = [unicodedata.normalize('NFD', re.sub(r'\s+','_',str(col).lower().strip())).encode('ascii', 'ignore').decode('utf-8') for col in old_cols]
        
        dataframe.columns = old_cols

        return dataframe