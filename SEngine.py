from engine.Engine import Engine
import logging
import sys

def main():
    if len(sys.argv) == 3:
        print("Initializing System, please wait...")
        username = sys.argv[1]
        password = sys.argv[2]
        eng = Engine(username, password)
    else:
        print("Initializing System, please wait...")
        eng = Engine()
    logging.getLogger().setLevel(logging.INFO)        
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