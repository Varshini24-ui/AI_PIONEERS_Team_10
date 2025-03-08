import gradio as gr
import pandas as pd
import re
import uuid
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# CSV File Names
csv_filename = "candidates.csv"
neutralized_csv_filename = "bias_free_hiring.csv"

# Function to neutralize gender terms in text
def neutralize_gender(text):
    gender_terms = {
        r'\bhe\b': 'they',
        r'\bshe\b': 'they',
        r'\bhim\b': 'them',
        r'\bher\b': 'them',
        r'\bhis\b': 'their',
        r'\bman\b': 'person',
        r'\bwoman\b': 'person',
        r'\bmen\b': 'people',
        r'\bwomen\b': 'people',
        r'\bboy\b': 'child',
        r'\bgirl\b': 'child',
        r'\bbusinessman\b': 'businessperson',
        r'\bbusinesswoman\b': 'businessperson',
    }
    for gender_term, neutral_term in gender_terms.items():
        text = re.sub(gender_term, neutral_term, text, flags=re.IGNORECASE)
    return text

# Function to check for plagiarism in text fields
def check_plagiarism(df, fields, threshold=0.8):
    """
    Check for plagiarism in specified fields using cosine similarity.
    Removes rows with similarity above the threshold.
    """
    try:
        # Ensure the specified fields exist in the DataFrame
        available_fields = [field for field in fields if field in df.columns]
        if not available_fields:
            return df  # No fields to check for plagiarism

        # Combine specified fields into a single text column for comparison
        df['combined_text'] = df[available_fields].apply(lambda row: ' '.join(row.values.astype(str)), axis=1)

        # Compute TF-IDF vectors
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(df['combined_text'])

        # Compute cosine similarity matrix
        similarity_matrix = cosine_similarity(tfidf_matrix)

        # Find duplicates based on similarity threshold
        duplicates = set()
        for i in range(len(similarity_matrix)):
            for j in range(i + 1, len(similarity_matrix)):
                if similarity_matrix[i, j] > threshold:
                    duplicates.add(j)

        # Remove duplicate rows
        df = df.drop(index=list(duplicates)).reset_index(drop=True)
        df = df.drop(columns=['combined_text'])  # Remove the temporary combined text column
        return df
    except Exception as e:
        print(f"Error checking plagiarism: {e}")
        return df

# Function to neutralize resume data, remove duplicates, and check for plagiarism
def neutralize_resume_data():
    try:
        # Read the original candidates.csv file
        df = pd.read_csv(csv_filename)
        
        # Remove duplicate rows based on 'Email' (you can change this to 'Phone Number' or another unique field)
        df = df.drop_duplicates(subset=['Email'], keep='first')

        # Neutralize gender terms in all string columns
        for col in df.columns:
            if pd.api.types.is_string_dtype(df[col]):
                df[col] = df[col].apply(neutralize_gender)

        # Remove name columns
        name_columns = [col for col in df.columns if re.search(r'name', col, re.IGNORECASE)]
        df = df.drop(columns=name_columns, errors='ignore')

        # Check for plagiarism in skills, experience, summary/profile, and GitHub projects
        plagiarism_fields = ['Skills', 'Experience (Years)', 'Summary', 'Projects']
        df = check_plagiarism(df, fields=plagiarism_fields)

        # Add a new Candidate ID column with unique UUIDs for each row
        df['Candidate ID'] = [str(uuid.uuid4()) for _ in range(len(df))]

        # Save the modified data to bias_free_hiring.csv
        df.to_csv(neutralized_csv_filename, index=False)
        return "Gender bias neutralized, duplicates removed, plagiarism checked, name columns removed, and saved to bias_free_hiring.csv with new Candidate IDs."
    except FileNotFoundError:
        return "Error: candidates.csv not found. Please ensure the file exists."
    except Exception as e:
        return f"Error neutralizing resumes: {e}"

# Function to match candidates with a job description
def match_candidates(job_description, num_candidates):
    try:
        # Read the neutralized CSV file
        df = pd.read_csv(neutralized_csv_filename)

        # Convert job description to lowercase for case-insensitive matching
        job_description = job_description.lower()

        # Calculate match scores
        match_scores = []
        for index, row in df.iterrows():
            resume_text = ' '.join(row.astype(str)).lower()
            match_score = sum(
                1 for word in job_description.split() 
                if word in resume_text
            )
            match_scores.append((row['Candidate ID'], match_score))

        # Rank candidates by match score
        ranked_candidates = sorted(match_scores, key=lambda x: x[1], reverse=True)

        # Limit the number of candidates to display
        ranked_candidates = ranked_candidates[:num_candidates]

        # Format the output
        output = "\n".join([f"Candidate ID: {candidate[0]}, Match Score: {candidate[1]}" for candidate in ranked_candidates])
        return output
    except FileNotFoundError:
        return "Error: bias_free_hiring.csv not found. Please neutralize resumes first."
    except Exception as e:
        return f"Error matching candidates: {e}"

# Automatically neutralize resumes when the app starts
neutralize_status = neutralize_resume_data()
print(neutralize_status)  # Print status to console

# Gradio Interface for Candidate Matching
with gr.Blocks() as demo:
    gr.Markdown("# Candidate Matching Tool")
    
    gr.Markdown("### Enter a job description and the number of candidates to rank.")
    job_description_input = gr.Textbox(lines=5, label="Job Description")
    num_candidates_input = gr.Number(label="Number of Candidates to Display", value=5, precision=0)
    match_button = gr.Button("Match Candidates")
    match_output = gr.Textbox(label="Top Candidates")
    
    match_button.click(
        fn=match_candidates,
        inputs=[job_description_input, num_candidates_input],
        outputs=match_output
    )

# Launch the app
demo.launch()
