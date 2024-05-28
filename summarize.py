import os
import re
import requests
import openai
import tiktoken
import fitz  # PyMuPDF
from dotenv import load_dotenv
from typing import Dict, List
from utilities import (
    num_tokens_from_messages,
    summarization_prompt_messages,
    split_text_into_sections,
    memoize_to_file,
)
import concurrent.futures

load_dotenv(".env")
openai.api_key = os.environ["OPENAI_API_KEY"]

# Define the global variable
actual_tokens = 0

def extract_text_from_pdf(pdf_path: str) -> str:
    print(f"Extracting text from PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    text = ""
    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        text += page.get_text("text")
    print(f"Extracted text length: {len(text)}")
    return text

def process_book(book_url: str = None, pdf_path: str = None) -> str:
    if book_url:
        print(f"Fetching book from URL: {book_url}")
        response = requests.get(book_url)
        if response.status_code != 200:
            return "Failed to fetch the book from the provided URL."
        book_complete_text = response.text
        book_complete_text = book_complete_text.replace("\r", "")
        split = re.split(r"\*\*\* .+ \*\*\*", book_complete_text)
        if len(split) < 2:
            return "Failed to process the book content."
        book = split[1]
        print(f"Book text length after processing URL: {len(book)}")
    elif pdf_path:
        book = extract_text_from_pdf(pdf_path)
        if not book:
            return "Failed to extract text from the PDF."
    else:
        return "No input provided."

    model_name = "gpt-3.5-turbo"
    enc = tiktoken.encoding_for_model(model_name)
    MAX_ATTEMPTS = 3

    num_tokens = len(enc.encode(book))
    division_point = "."

    summaries = {}
    target_summary_sizes = [500, 750, 1000]

    intermediate_summaries = []
    chunk_size = 3000  # Adjust this size as needed

    # Split book into larger chunks for intermediate summaries
    split_input = split_text_into_sections(
        book, chunk_size, division_point, model_name
    )

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                summarize,
                x,
                summarization_token_parameters(
                    target_summary_size=max(target_summary_sizes), model_context_size=4097
                ),
                division_point,
                model_name,
            )
            for x in split_input
        ]

        for future in concurrent.futures.as_completed(futures):
            try:
                intermediate_summaries.append(future.result().replace("[[[", "").replace("]]]", ""))
            except Exception as exc:
                print(f"Generated an exception: {exc}")

    # Combine intermediate summaries and create final summary
    combined_text = "\n\n".join(intermediate_summaries)
    final_summary = synthesize_summaries([combined_text], "gpt-4")  # Use a powerful model for synthesis
    return final_summary

def gpt_summarize(text: str, target_summary_size: int) -> str:
    global actual_tokens
    tries = 0
    while True:
        try:
            tries += 1
            print(f"Attempting to summarize text. Attempt: {tries}")
            result = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=summarization_prompt_messages(text, target_summary_size),
            )
            actual_tokens += result['usage']['total_tokens']
            return "[[[" + result['choices'][0]['message']['content'] + "]]]"
        except openai.error.OpenAIError as e:
            if tries >= MAX_ATTEMPTS:
                print(f"OpenAI exception after {MAX_ATTEMPTS} tries. Aborting. {e}")
                raise e
            if not e.should_retry:
                print(f"OpenAI exception with should_retry false. Aborting. {e}")
                raise e
            else:
                print(f"Summarize failed (Try {tries} of {MAX_ATTEMPTS}). {e}")
                random_wait = (
                    random.random() * 4.0 + 1.0
                )  # Wait between 1 and 5 seconds
                random_wait = (
                    random_wait * tries
                )  # Scale that up by the number of tries (more tries, longer wait)
                time.sleep(random_wait * tries)

from dataclasses import dataclass

@dataclass(frozen=True, repr=True)
class SummarizationParameters:
    target_summary_size: int
    summary_input_size: int

def summarization_token_parameters(
    target_summary_size: int, model_context_size: int
) -> SummarizationParameters:
    base_prompt_size = num_tokens_from_messages(
        summarization_prompt_messages("", target_summary_size), model=model_name
    )
    summary_input_size = model_context_size - (base_prompt_size + target_summary_size)
    return SummarizationParameters(
        target_summary_size=target_summary_size,
        summary_input_size=summary_input_size,
    )

@memoize_to_file(cache_file="cache.json")
def summarize(
    text: str,
    token_quantities: SummarizationParameters,
    division_point: str,
    model_name: str,
) -> str:
    text_to_print = re.sub(r" +\|\n\|\t", " ", text).replace("\n", "")
    print(
        f"\nSummarizing {len(enc.encode(text))}-token text: {text_to_print[:60]}{'...' if len(text_to_print) > 60 else ''}"
    )

    if len(enc.encode(text)) <= token_quantities.target_summary_size:
        return text
    elif len(enc.encode(text)) <= token_quantities.summary_input_size:
        summary = gpt_summarize(text, token_quantities.target_summary_size)
        print(
            f"Summarized {len(enc.encode(text))}-token text into {len(enc.encode(summary))}-token summary: {summary[:250]}{'...' if len(summary) > 250 else ''}"
        )
        return summary
    else:
        split_input = split_text_into_sections(
            text, token_quantities.summary_input_size, division_point, model_name
        )

        summaries = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(summarize, x, token_quantities, division_point, model_name)
                for x in split_input
            ]
            for future in concurrent.futures.as_completed(futures):
                summaries.append(future.result())

        return summarize(
            "\n\n".join(summaries), token_quantities, division_point, model_name
        )

@memoize_to_file(cache_file="cache.json")
def synthesize_summaries(summaries: List[str], model: str) -> str:
    print(f"Synthesizing {len(summaries)} summaries into a single summary.")

    summaries_joined = ""
    for i, summary in enumerate(summaries):
        summaries_joined += f"Summary {i + 1}: {summary}\n\n"

    messages = [
        {
            "role": "user",
            "content": f"""
A less powerful GPT model generated {len(summaries)} summaries of a book.

Because of the way that the summaries are generated, they may not be perfect. Please review them
and synthesize them into a single more detailed summary that you think is best.

The summaries are as follows: {summaries_joined}
""".strip(),
        },
    ]

    assert num_tokens_from_messages(messages, model=model_name) <= 8192
    print(messages)

    result = openai.ChatCompletion.create(
        model=model,
        messages=messages,
    )
    return result['choices'][0]['message']['content']

model_name = "gpt-3.5-turbo"
enc = tiktoken.encoding_for_model(model_name)
