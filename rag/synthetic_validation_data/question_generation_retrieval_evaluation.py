import json
import os

# For cost-saving, create a cache for the LLM responses
import threading

# For data analysis and visualization
import matplotlib.pyplot as plt
import numpy as np
import openai
import pandas as pd

# For scraping
import requests
import seaborn as sns
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import CharacterTextSplitter
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE

# Load environment variables from .env file
load_dotenv()

# Set up OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = openai.api_key

# Choose a seed for reproducible results
SEED = 2023

# For cost-saving purposes, choose a path to persist the responses for LLM calls
CACHE_PATH = "_cache.json"
EMBEDDINGS_CACHE_PATH = "_embeddings_cache.json"

# To avoid re-running the scraping process, choose a path to save the scrapped docs
GENERATED_DATA_PATH = "generated_emails.json"

# Choose a path to save the generated dataset
OUTPUT_DF_PATH = "question_answer_source.csv"


class Cache:
    """
    A class for caching API responses to avoid redundant calls.
    """

    def __init__(self, persist_path, cache_loading_fn):
        """
        The cache_loading_fn should be a function that takes arbitrary
        serializable arguments and returns a serilaizable value.
          value = cache_loading_fn(**kwargs)
        For example, for openai.chat.completions.create(...), the
        cache_loading_fn should be:
          def cache_loading_fn(**kwargs):
            result = openai.chat.completions.create(**kwargs)
            return result.to_dict_recursive()
        """
        self._cache = self._get_or_create_cache_dict(persist_path)
        self._persist_path = persist_path
        self._cache_loading_fn = cache_loading_fn
        self._cache_lock = threading.Lock()

    @classmethod
    def _get_or_create_cache_dict(cls, persist_path):
        """Load cache from file if exists, otherwise create empty cache"""
        if os.path.exists(persist_path):
            # File exists, load it as a JSON string into a dict
            with open(persist_path) as f:
                cache = json.load(f)
        else:
            # File does not exist, create an empty dict
            cache = {}
        return cache

    def _save_to_file(self):
        """Save current cache to file"""
        with open(self._persist_path, "w") as file:
            json.dump(self._cache, file)

    def _update_cache(self, key, value):
        """Thread-safe update of cache"""
        with self._cache_lock:
            self._cache[key] = value
            self._save_to_file()

    def get_from_cache_or_load_cache(self, **kwargs):
        """Get from cache if exists, otherwise call function and update cache"""
        key = json.dumps(kwargs)

        with self._cache_lock:
            value = self._cache.get(key, None)

        if value is None:
            value = self._cache_loading_fn(**kwargs)
            self._update_cache(key, value)
        else:
            print("Loaded from cache")

        return value


def chat_completion_create_fn(**kwargs):
    """Function to create OpenAI chat completion and extract function call arguments"""
    result = openai.chat.completions.create(**kwargs)
    # print("Created new chat completion", result.choices[0].message)
    return result.choices[0].message.function_call.arguments


def cached_openai_ChatCompletion_create(**kwargs):
    """Wrapper for cached OpenAI chat completion"""
    cache = kwargs.pop("cache")
    return cache.get_from_cache_or_load_cache(**kwargs)


def embeddings_embed_documents_fn(**kwargs):
    """Function to create document embeddings"""
    chunk = kwargs.get("chunk")
    return embeddings.embed_documents([chunk])


def cached_langchain_openai_embeddings(**kwargs):
    """Wrapper for cached embeddings"""
    cache = kwargs.pop("cache")
    return cache.get_from_cache_or_load_cache(**kwargs)


def get_raw_response(content):
    """Get response from OpenAI for question generation"""
    prompt = f"""Please generate a question asking for the key information in the given email.
    Also answer the questions using the information in the given email.
    Please ask the specific question instead of the general question, like
    'What is the key information in the given email?'.
    Please generate the answer using as much information as possible.
    If you are unable to answer it, please generate the answer as 'I don't know.'
    The answer should be informative and should be more than 3 sentences.

    Email: {content}

    Please call the submit_function function to submit the generated question and answer.
    """

    messages = [{"role": "user", "content": prompt}]

    submit_function = {
        "name": "submit_function",
        "description": "Call this function to submit the generated question and answer.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question asking for the key information in the given email.",
                },
                "answer": {
                    "type": "string",
                    "description": "The answer to the question using the information in the given email.",
                },
            },
            "required": ["question", "answer"],
        },
    }

    response = cached_openai_ChatCompletion_create(
        messages=messages,
        model="gpt-4o-mini",
        functions=[submit_function],
        function_call="auto",
        temperature=0.0,
        seed=SEED,
        cache=cache,
    )
    # print("Response: ", response)
    return response


def generate_question_answer(content):
    """Generate a question and answer based on the given content"""
    if content is None or len(content) == 0:
        return "", "N/A"

    response = get_raw_response(content)
    # print(response)
    try:
        func_args = json.loads(response)
        question = func_args["question"]
        answer = func_args["answer"]
        return question, answer
    except Exception as e:
        return str(e), "N/A"


def add_to_output_df(result_df=pd.DataFrame({})):
    """
    This function adds the records in result_df to the existing records saved at OUTPUT_DF_PATH,
    remove the duplicate rows and save the new collection of records back to OUTPUT_DF_PATH.
    """
    if os.path.exists(OUTPUT_DF_PATH):
        all_result_df = pd.read_csv(OUTPUT_DF_PATH)
    else:
        all_result_df = pd.DataFrame({})
    all_result_df = (
        pd.concat([all_result_df, result_df], ignore_index=True)
        .drop_duplicates()
        .sort_values(by=["email", "chunk_id"])
        .reset_index(drop=True)
    )
    all_result_df.to_csv(OUTPUT_DF_PATH, index=False)
    return all_result_df


def cossim(x, y):
    """Calculate cosine similarity between two vectors"""
    return np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y))


def main():
    """Main function to run the question generation and evaluation pipeline"""
    # Load generated email data
    with open(GENERATED_DATA_PATH) as data_file:
        data = json.load(data_file)

    df = pd.json_normalize(data)

    # Generate questions and answers for each email
    queries = []
    n = len(df)
    for i, row in df.iterrows():
        chunk = row["content.plain_text"]
        question, answer = generate_question_answer(chunk)
        # print(f"{i + 1}/{n}: {question}")
        queries.append(
            {
                "question": question,
                "answer": answer,
                "email": chunk,
                "chunk_id": row["metadata.message_id"],
                "topic": row["analytics.topic"],
                "industry": row["analytics.industry"],
            }
        )

    # Create and filter dataframe
    result_df = pd.DataFrame(queries)
    result_df = result_df[result_df["answer"] != "N/A"]

    # Combine with existing results
    all_result_df = add_to_output_df(result_df)

    # Analyze question length distribution
    questions = all_result_df["question"].to_list()
    question_len = pd.DataFrame([len(q) for q in questions], columns=["length"])
    question_len.hist(bins=5)
    plt.title("Histogram of Question Lengths")
    plt.xlabel("Question Length")
    plt.ylabel("Frequency")
    plt.show()

    p10 = int(question_len["length"].quantile(0.10))
    p90 = int(question_len["length"].quantile(0.90))
    print("p10-p90 range is", p90 - p10)

    # Define benchmark questions for comparison
    benchmark_questions = [
        "What services does Elliot Management Solutions offer to improve customer support at Davidson Supermarkets?",
        "What are the details of the exclusive Masterclass on Advanced Retail Sales Pitches mentioned in the email?",
        "What are the details of the conference titled 'Amplifying Sales Through Effective Pitches' mentioned in the email?",
        "What are the details and purpose of the 'Retail Evolution Summit 2022' invitation extended to Ms. Claire Sanders?",
        "What are the key details of the 'Transforming Retail - Strategy and Innovation Summit' mentioned in the email?",
        "What are the details of the 'Sales Pitches: Retail Industry Edition' workshop mentioned in the email?",
        "What are the key details regarding the latest technical documentation update for ABC Retail Corporation?",
        "What are the details and purpose of the Mastering Retail Sales Pitches workshop mentioned in the email?",
        "What details are provided about the upcoming release of the updated Technical Documentation for the retail sector?",
        "What insights does John Preston provide regarding the retail industry's financial performance for Q2?",
    ]
    questions_to_embed = questions + benchmark_questions

    # Apply embeddings
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    question_embeddings = embeddings.embed_documents(questions)

    # Dimension reduction for visualization
    # PCA on embeddings to reduce to 10-dim
    pca = PCA(n_components=10, random_state=SEED)
    question_embeddings_reduced = pca.fit_transform(question_embeddings)
    # TSNE on embeddings to reduce to 2-dim
    tsne = TSNE(n_components=2, perplexity=10, max_iter=1000, random_state=SEED)
    lower_dim_embeddings = tsne.fit_transform(question_embeddings_reduced)

    # Visualize embeddings
    labels = np.concatenate(
        [
            np.full(len(lower_dim_embeddings) - len(benchmark_questions), "generated"),
            np.full(len(benchmark_questions), "benchmark"),
        ]
    )
    data = pd.DataFrame(
        {
            "x": lower_dim_embeddings[:, 0],
            "y": lower_dim_embeddings[:, 1],
            "label": labels,
        }
    )
    sns.scatterplot(data=data, x="x", y="y", hue="label")

    # Calculate embeddings for questions and chunks
    embedded_queries = all_result_df.copy()
    embedded_queries["chunk_emb"] = all_result_df["email"].apply(
        lambda x: np.squeeze(
            cached_langchain_openai_embeddings(chunk=x, cache=embeddings_cache)
        )
    )
    embedded_queries["question_emb"] = all_result_df["question"].apply(
        lambda x: np.squeeze(
            cached_langchain_openai_embeddings(chunk=x, cache=embeddings_cache)
        )
    )

    # Calculate cosine similarity between questions and their source chunks
    embedded_queries["cossim"] = embedded_queries.apply(
        lambda row: cossim(row["question_emb"], row["chunk_emb"]), axis=1
    )

    # Visualize similarity scores
    scores = embedded_queries["cossim"].to_list()
    plt.hist(scores, bins=5)

    # Print examples of low similarity questions
    mask = embedded_queries["cossim"] < 0.55
    lower_cossim = embedded_queries[mask]
    for i, row in lower_cossim.iterrows():
        print(f"Question: {i}")
        print(row["question"])
        print("Chunk:")
        print(row["email"])
        print("cossim:")
        print(row["cossim"])
