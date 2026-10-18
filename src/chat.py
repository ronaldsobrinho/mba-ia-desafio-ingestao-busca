from search import search_prompt

EXIT_COMMANDS = {"sair", "exit", "quit"}


def main():
    chain = search_prompt()

    if not chain:
        print("Não foi possível iniciar o chat. Verifique os erros de inicialização.")
        return

    print("Faça sua pergunta (digite 'sair' para encerrar):")
    while True:
        try:
            question = input("\nPERGUNTA: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if not question:
            continue
        if question.lower() in EXIT_COMMANDS:
            break

        try:
            answer = chain.invoke(question)
        except Exception as e:
            print(f"Erro ao processar a pergunta: {e}")
            continue

        print(f"RESPOSTA: {answer}")


if __name__ == "__main__":
    main()
