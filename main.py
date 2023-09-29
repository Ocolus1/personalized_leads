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

# Template for LinkedIn scraping logic
def scrape_linkedin_info(driver, url):
    try:
        driver.get(url)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        # Extract relevant information from LinkedIn Profile
        # The actual tags and classes would depend on LinkedIn's current page structure
        # Return the scraped information
        
    except Exception as e:
        print(f"Error scraping LinkedIn {url}: {str(e)}")
        return None

# Function to send prompt to GPT and get a response
def get_gpt_response(meta_description, page_title, company_name, campaign, offer, industry):
    prompt = f"""
    Generate a personalized one sentence message for the person based on this information on their website.
    Find something unique from the info above. We are doing a {campaign} {industry} campaign,
    and the intention is to be very informal, like an old friend calling up to see something interesting
    and unique from their info, and using that to connect back to what we're offering to get them on a call with us.
    We are offering {offer}.
    [Meta Description: {meta_description}]
    [Page Title: {page_title}]
    [Company Name: {company_name}]
    """
    try:
        # Make an API call to OpenAI to get a response
        response = openai.Completion.create(
            engine="text-davinci-003",  
            prompt=prompt,
            temperature=0.6,
            max_tokens=100,
        )
        
        # Extract and return the response
        return response.choices[0].text.strip()
    
    except Exception as e:
        print(f"Error getting response from GPT: {str(e)}")
        return None

def main():
    st.title('Personalized Leads Generator')
    
    # Adding new inputs
    scrape_source = st.radio('Choose the source to scrape:', ('Website URL', 'LinkedIn'), index=0)
    campaign = st.radio('What kind of campaign is this?', ('Database Reactivation', 'Cold outreach'))
    offer = st.text_input('What are you offering?')
    industry = st.text_input('What industry are you in?')
    
    contacts_options = {'All': 'all', 'Half': 'half', '10': 10, '20': 20, '50': 50}
    contacts_to_personalize = st.radio('How many contacts do you want to personalize for?', list(contacts_options.keys()), key='contacts', horizontal=True)
    
    uploaded_file = st.file_uploader("Upload a CSV file containing company names and their websites", type="csv")
    
    if uploaded_file is not None:
        # Load the CSV file
        input_df = pd.read_csv(uploaded_file)
        
        # Drop empty rows and columns
        input_df.dropna(how='all', inplace=True)  # Drop empty rows
        input_df.dropna(axis=1, how='all', inplace=True)  # Drop empty columns
        
        # Define a pattern to identify rows where email contains the word "test"
        pattern_test = re.compile(r'\btest\b', re.IGNORECASE)

        # Clean the DataFrame
        cleaned_df = input_df.dropna(subset=['email', 'website'], how='any')
        cleaned_df = cleaned_df[~cleaned_df['email'].str.contains(pattern_test)]
        cleaned_df = cleaned_df[~cleaned_df['companyName'].apply(is_gibberish)]
        
        # Initialize new columns for Meta Description, Page Title, and Personalization
        cleaned_df['personalization'] = None
        
        # Initialize the web driver
        options = Options()
        options.add_argument("--headless")
        driver = uc.Chrome(executable_path=ChromeDriverManager().install(), options=options)
        
        total = len(cleaned_df.index)
        
        # Update total based on user selection
        if contacts_options[contacts_to_personalize] == 'half':
            total = total // 2
        elif contacts_options[contacts_to_personalize].isdigit():
            total = min(total, int(contacts_options[contacts_to_personalize]))

        
        progress = st.progress(0)
        
        # Iterate over the rows of the dataframe and scrape information
        for index, (idx, row) in enumerate(cleaned_df.iterrows()):
            # Break the loop if index is equal to total
            if index == total:
                break
            
            print(f"Getting the link of {index} item of {total} items")
            # Update the progress bar
            progress.progress((index + 1) / total)
            
            
            company_name = row['companyName']
            url = row['LinkedIn URL'] if scrape_source == "LinkedIn" else row['website']
            
            # Scrape information based on user selection
            if scrape_source == 'LinkedIn':
                linkedin_info = scrape_linkedin_info(driver, url)
                message = get_gpt_response(linkedin_info, company_name, campaign, offer, industry)
            else:
                meta_description, page_title = scrape_website_info(driver, url)
                message = get_gpt_response(meta_description, page_title, company_name, campaign, offer, industry)
                
            if message:
                cleaned_df.at[idx, 'personalization'] = message
            
        
        # Complete the progress bar once scraping is finished
        progress.progress(total/total)  
        
        # Save the cleaned DataFrame with scraped information and Personalization to a new CSV file
        cleaned_df.to_csv('output.csv', index=False, quoting=csv.QUOTE_NONE, escapechar='\\')
        
        print("Finished getting all the personalized leads")
        
        # Close the driver
        driver.quit()
        
        # Show the first five rows of the result and provide download link
        st.write('Processed DataFrame:')
        st.write(cleaned_df.head())
        csv_data = cleaned_df.to_csv(index=False)
        b64 = base64.b64encode(csv_data.encode()).decode()  
        href = f'<a href="data:file/csv;base64,{b64}" download="output.csv">Download Processed CSV File</a>'
        st.markdown(href, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
