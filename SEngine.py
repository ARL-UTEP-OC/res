from engine.Engine import Engine

def main():
    eng = Engine.getInstance()
    while True:
        try:
            command_line = input(">> ")
            if command_line == "exit" or command_line == "quit" or command_line == "q" or command_line == "exit()":
                break
            print(str(eng.execute(command_line)))
        except SystemExit:
            # break
            print(f"Error: bad input command")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()