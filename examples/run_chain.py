import os
from chains.symptom_parser import make_parser_chain, run_parser


def main():
    api_key = os.getenv('GENAI_API_KEY')
    chain = make_parser_chain(api_key=api_key)

    sample = "I have a sore throat, fever of 101F, runny nose, and mild headache."

    print('Running symptom parser on sample:')
    print(sample)

    parsed = run_parser(chain, sample)
    print('\nParsed result:')
    print(parsed.json(indent=2))


if __name__ == '__main__':
    main()
