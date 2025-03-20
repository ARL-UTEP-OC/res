from engine.Engine import Engine

def main():
    print("Initializing System, please wait...")
    eng = Engine.getInstance()
    print("Done")
    while True:
        try:
            command_line = input(">> ")
            if command_line == "exit" or command_line == "quit" or command_line == "q" or command_line == "exit()":
                break
            elif command_line.strip() == "":
                continue
            print("executing, please wait...")
            print(str(eng.execute(command_line)))
        except SystemExit:
            # break
            print(f"Error: bad input command")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()