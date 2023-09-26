import streamlit as st
import pandas as pd
import re
import csv
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import openai
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import base64
import os

# Set up the OpenAI API key
openai.api_key = os.getenv('OPENAI_API_KEY')

# Function to check if a string is gibberish
def is_gibberish(name):
    vowels = set("AEIOUaeiou")
    if name and not any(char in vowels for char in name):
        return True
    return False

# Function to scrape Meta Description and Page Title from a website
def scrape_website_info(driver, url):
    try:
        driver.get(url)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Get Meta Description
        meta_description = None
        meta_tag = soup.find('meta', attrs={'name': 'description'})
        if meta_tag:
            meta_description = meta_tag.get('content')
        
        # Get Page Title
        page_title = soup.title.string if soup.title else None
        
        return meta_description, page_title
    
    except Exception as e:
        print(f"Error scraping {url}: {str(e)}")
        return None, None
    

# Function to send prompt to GPT and get a response
def get_gpt_response(meta_description, page_title, company_name):
    prompt = f"""
    [Meta Description: {meta_description}]
    [Page Title: {page_title}]
    
    Generate a personalized one-line sentence to approach a potential client based on the given Meta Description and Page Title for the company {company_name}.
    """
    
    try:
        # Make an API call to OpenAI to get a response
        response = openai.Completion.create(
            engine="text-davinci-003",  # You can use "davinci" for GPT-3 or the equivalent for GPT-4
            prompt=prompt,
            temperature=0.6,
            max_tokens=100,
        )
        
        # Extract and return the response text
        return response.choices[0].text.strip()
    
    except Exception as e:
        print(f"Error getting response from GPT: {str(e)}")
        return None




def main(driver, df):
    # Load the CSV file into a DataFrame
    # file_path = 'wer.csv'
    # df = pd.read_csv(file_path)

    # Define a pattern to identify rows where email contains the word "test"
    pattern_test = re.compile(r'\btest\b', re.IGNORECASE)

    # Clean the DataFrame
    cleaned_df = df.dropna(subset=['email', 'website'], how='any')
    cleaned_df = cleaned_df[~cleaned_df['email'].str.contains(pattern_test)]
    cleaned_df = cleaned_df[~cleaned_df['companyName'].apply(is_gibberish)]

    
    try :
        # Initialize new columns for Meta Description, Page Title, and Personalization
        cleaned_df['personalization'] = None
        
        # Initialize the progress bar
        progress = st.progress(0)
        total = len(cleaned_df.index)

        # Loop through the cleaned DataFrame and scrape website information
        for index, row in cleaned_df.iterrows():
            url = row['website']
            print(f"Getting the {index} url : {url}")
            meta_description, page_title = scrape_website_info(driver, url)
            company_name = row['companyName']
            
            # Get the personalized line from GPT and store it in the DataFrame
            personalized_line = get_gpt_response(meta_description, page_title, company_name)
            if personalized_line:
                cleaned_df.at[index, 'personalization'] = personalized_line
                
            # Update the progress bar
            progress.progress((index + 1) / total)

        # Save the cleaned DataFrame with scraped information and Personalization to a new CSV file
        cleaned_df.to_csv('output.csv', index=False, quoting=csv.QUOTE_NONE, escapechar='\\')
        
        print("Finished getting all the personalized leads")
    except Exception as e:
        print(f"Error : {str(e)}")
        
    # Complete the progress bar once scraping is finished
    progress.progress(total)
        
    return cleaned_df


if __name__ == '__main__':
    st.title("Website Scraper and Personalizer")
    
    # Upload the input CSV file
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
    if uploaded_file is not None:
        input_df = pd.read_csv(uploaded_file)
        
        # Drop empty rows and columns
        input_df.dropna(how='all', inplace=True)  # Drop empty rows
        input_df.dropna(axis=1, how='all', inplace=True)  # Drop empty columns
        
        # Show only the first five rows of the uploaded DataFrame
        st.write('Uploaded CSV (Empty rows and columns removed):')
        st.write(input_df.head())
        
        # Initialize the undetected_chromedriver and run the main function
        options = Options()
        options.add_argument('-start-maximized')
        driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
        output_df = main(driver, input_df)
        driver.quit()
        
        # Show the first five rows of the result and provide download link
        st.write('Processed DataFrame:')
        st.write(output_df.head())
        csv = output_df.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()  
        href = f'<a href="data:file/csv;base64,{b64}" download="output.csv">Download Processed CSV File</a>'
        st.markdown(href, unsafe_allow_html=True)