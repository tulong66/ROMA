import os
import base64
import hashlib
import pandas as pd
import time
import sys
import re

from openai import OpenAI

GRADER_TEMPLATE = """
Judge whether the following [response] to [question] is correct or not based on the precise and unambiguous [correct_answer] below.

[question]: {question}

[response]: {response}

Your judgement must be in the format and criteria specified below:

extracted_final_answer: The final exact answer extracted from the [response]. Put the extracted answer as 'None' if there is no exact, final answer to extract from the response.

[correct_answer]: {correct_answer}

reasoning: Explain why the extracted_final_answer is correct or incorrect based on [correct_answer], focusing only on if there are meaningful differences between [correct_answer] and the extracted_final_answer. Do not comment on any background to the problem, do not attempt to solve the problem, do not argue for any answer different than [correct_answer], focus only on whether the answers match.

correct: Answer 'yes' if extracted_final_answer matches the [correct_answer] given above, or is within a small margin of error for numerical problems. Answer 'no' otherwise, i.e. if there if there is any inconsistency, ambiguity, non-equivalency, or if the extracted answer is incorrect.
""".strip()

CHOICE_STRINGS = ["yes", "no"]


#MODEL_GPT_4O = "openai/gpt-4o"
#MODEL_DEEPSEEK_R1 = "deepseek/deepseek-reasoner"
#name = "CodeActSolver"



client = OpenAI(api_key= os.environ.get("FIREWORKS_AI_API_KEY", None), base_url="https://api.fireworks.ai/inference/v1")

#print(os.environ.get("FIREWORKS_AI_API_KEY", None))

BATCH_SIZE = 30
batch_count = 1  # start from 1 for agent_comparisons30.csv
inputs = []  # list to store inputs
results = []
#N = 1  # for example, pick 15 entries

curr_work_id = 1
existing_filename = f"seal_0_final_pro_30_example_longer_results.csv"
processed_problems = set()

#batches = [0,315,630,945,1266]
#start_idx = batches[curr_work_id - 1]
#end_idx = batches[curr_work_id]
#start_idx = 0
#end_idx = 50
if os.path.exists(existing_filename):
    try:
        existing_df = pd.read_csv(existing_filename)
        #sliced_df = existing_df.iloc[start_idx:end_idx]
        print(existing_df)
        #print(sliced_df)
        for _, row in existing_df.iterrows():
            inputs.append(row.to_dict())  # Add to the inputs list
    except Exception as e:
        print(f"Error loading existing CSV: {e}")

#print(inputs[0])

MODEL_EVAL = "accounts/fireworks/models/deepseek-r1-0528"
print(f"CURR WORK ID: {curr_work_id}")
print("\n\n\n")
print(MODEL_EVAL)
# Step 2: Filter sampled_df
#sampled_df = df.sample(n=N)[['problem', 'answer', 'canary']]
print(len(inputs))
'''for idx, row in sampled_df.iterrows():
    problem = decrypt(row.get("problem", ""), row.get("canary", ""))
    answer = decrypt(row.get("answer", ""), row.get("canary", ""))
    #problem = row['problem']
    #answer = row['answer']
    print(f"problem: {problem}")
    print(f"answer: {answer}")'''

count = 0
correct_count = 0
print("----------------- START OF AGENT EXECUTION -----------------")
for row in inputs:
    count += 1
    try:
        problem = row["question"].split("Your response should be in the following format:")[0]
        prompt = f"""
    Judge whether the following [response] to [question] is correct or not based on the precise and unambiguous [correct_answer] below.

    [question]: {problem}

    [response]: {row["result"]}

    Your judgement must be in the format and criteria specified below:

    extracted_final_answer: The final exact answer extracted from the [response]. Put the extracted answer as 'None' if there is no exact, final answer to extract from the response.

    [correct_answer]: {row["answer"]}

    reasoning: Explain why the extracted_final_answer is correct or incorrect based on [correct_answer], focusing only on if there are meaningful differences between [correct_answer] and the extracted_final_answer. Do not comment on any background to the problem, do not attempt to solve the problem, do not argue for any answer different than [correct_answer], focus only on whether the answers match.

    correct: Answer 'yes' if extracted_final_answer matches the [correct_answer] given above, or is within a small margin of error for numerical problems. Answer 'no' otherwise, i.e. if there if there is any inconsistency, ambiguity, non-equivalency, or if the extracted answer is incorrect.
    """.strip()
        response = client.chat.completions.create(
            model=MODEL_EVAL,
            messages=[
                {"role": "system", "content": "You are a strict, high-precision evaluation assistant. Your job is to assess the correctness of answers by comparing model-generated responses against authoritative correct answers. You must focus only on whether the final answer matches, without solving the problem or adding any commentary. Be objective, literal, and rule-following."},
                {"role": "user", "content": prompt},
            ],
            stream=False
        )
        model_ans = response.choices[0].message.content
        match = re.search(r"correct:\s*(yes|no)", model_ans, re.IGNORECASE)
        if match:
            is_correct_str = match.group(1).lower()  # "yes" or "no"
            is_correct = 1 if is_correct_str == "yes" else 0
            correct_count += is_correct
        else:
            is_correct = None  # or handle missing value
        print(f"PROMPT: {prompt}")
        print(f"FINAL ANSWER: {model_ans}")
        print(f"IS CORRECT: {is_correct}")
        print("\n\n\n")

        results.append({
            'problem': problem,
            'agent_answer': row["result"],
            'full_answer': model_ans,
            'correct_answer': row["answer"],
            'is_correct': is_correct
        })
        if len(results) % BATCH_SIZE == 0:
                filename = f'evals/test_results/final_results_search_pro_seal_0_no_reasoning_longer_context_temp_{curr_work_id}_{len(results)}.csv'
                results_df = pd.DataFrame(results)
                results_df.to_csv(filename, index=False)
                print(f"Saved batch to {filename}")

                batch_count += 1  # optional if you want to track further
        #time.sleep(3)
    except Exception as e:
        print(f"Error at index {count}: {e}")
        continue


print(count)
results_df = pd.DataFrame(results)
results_df.to_csv(f'final_results_pro_seal_0_30_{curr_work_id}.csv', index=False)
print(f"TOTAL CORRECT COUNT: {correct_count}/{len(results)}")