import sys, os, time, shutil, subprocess, json, urllib, getpass
from itertools import cycle

try:
    import spotipy
    import urllib3
    from pynput.keyboard import Key, Controller
except ImportError:
    print("DEPENDENCIES NOT INSTALLED!"
          "\nPlease install the depenencies by running:"
          "\n\t`python -m pip install -r requirements.txt`")
    sys.exit(1)

#Vars
keyboard = Controller()

def closeSpotify():
    if os.name == "nt":  # windows
        os.system("taskkill /f /im spotify.exe")
    elif sys.platform == "darwin":  # Mac OS
        # Not exactly sure of the process name, so used regex.
        os.system("killall -9 -r [Ss]potify.*")
    else:  # almost everything else
        os.system("killall -9 spotify")

def openSpotify(path):
    subprocess.Popen([path], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)

def playPause():
    keyboard.press(Key.media_play_pause)
    keyboard.release(Key.media_play_pause)

def nextTrack():
    keyboard.press(Key.media_next)
    keyboard.release(Key.media_next)
    
def previousWindow():
    keyboard.press(Key.alt_l)
    keyboard.press(Key.tab)
    keyboard.release(Key.alt_l)
    keyboard.release(Key.tab)
    
def restartSpotify(path):
    closeSpotify()
    openSpotify(path)
    time.sleep(5)
    nextTrack()
    previousWindow()

def xor_crypt(data, key):
    return ''.join(chr(ord(x) ^ ord(y)) for (x,y) in zip(data, cycle(key)))

def is_ascii(s):
    return all(ord(c) < 128 for c in s)

def setupSpotifyObject(username, scope, clientID, clientSecret, redirectURI):
    token = spotipy.util.prompt_for_user_token(username, scope, clientID,
                                               clientSecret, redirectURI)
    return spotipy.Spotify(auth=token)

def main(username, scope, clientID, clientSecret, redirectURI, path):    
    try:
        spotify = setupSpotifyObject(username, scope, clientID, clientSecret, redirectURI)
    except (OSError, urllib3.exceptions.HTTPError) as e:
        print(f"\nSomething went wrong: {e}\n")
        print("Please connect to the internet and run the program again.")
        return

    print("\nAwesome, that's all I needed. I'm watching for ads now <.<")
    restartSpotify(path)

    current_track = None
    last_track = ""
    while True:
        try:
            try:
                try:
                    current_track = spotify.current_user_playing_track()
                except spotipy.SpotifyException:
                    print('Token expired')
                    spotify = setupSpotifyObject(username, scope, clientID, clientSecret, redirectURI)
                    current_track = spotify.current_user_playing_track()

            except (OSError, urllib3.exceptions.HTTPError) as e:
                print(f"\nSomething went wrong: {e}\n")
                print("Waiting for network connection...")
                while True:
                    time.sleep(5)
                    try:  # Test network
                        urllib.request.urlopen("https://spotify.com", timeout=5)
                    except OSError:
                        pass
                    else:
                        print("Connection restored!")
                        break

            if current_track:  # Can either be `None` or JSON data `dict`.
                if current_track['currently_playing_type'] == 'ad':
                    restartSpotify(path)
                    print('Ad skipped')
                    continue  # get new track info

                if current_track['item']['name'] != last_track:  # Next track
                    # Current track's remaining duration
                    wait = current_track["item"]['duration_ms'] - current_track['progress_ms']

                    try:
                        # Reduces API requests to prevent getting rate limited from spotify API
                        time.sleep(wait/1000 - 8)  # until **almost** the end of the current track
                        last_track = current_track['item']['name']
                    except KeyboardInterrupt:
                        print("\n1. Skip track.\n"
                              "2. Want to change playlist/track or pause playback.\n"
                              "3. Exit this program (enter anything else).\n"
                             )
                        choice = input("Choose an option (1/2/?): ")
                        last_track = ""  # In case the track remains the same.
                        if choice == '1':
                            nextTrack()
                            playPause()  # To prevent ads from playing during the delay below.
                            # A short delay is required for the Spotify API to register the
                            # track change, so as to get the correct track info on the next request.
                            time.sleep(0.6)  # 600ms seems to be the shortest possible
                            playPause()
                        elif choice == '2':
                            input("You can go ahead to change the playlist/track"
                                  " or pause the playback on the Spotify app.\n"
                                  "Press ENTER after changing the playlist/track"
                                  " or resuming playback...")
                            print("Resuming my business of skipping ads ;)")
                        else:
                            sys.exit(0)
                        continue  # Skip the one-second sleep

            time.sleep(1)
        except KeyboardInterrupt:
            if input("\nExit? (Y/n) ").lower() != 'n':
                break
            print("Resuming my business of skipping ads ;)")


if __name__ == '__main__':
    # These are kinda constants

    # Popen expects a path-like object, `None` results in an error.
    PATH = (shutil.which("spotify")  # For any system with spotify on $PATH
            or ("{HOMEDRIVE}{HOMEPATH}\AppData\Roaming\Spotify\Spotify.exe"
                .format_map(os.environ) if os.name == "nt"  # Windows
                else "/Applications/Spotify.app" if sys.platform == "darwin"  # MacOS
                else ""  # Custom path if installation is different
               )
           )

    spotifyAccessScope = "user-read-currently-playing"
    spotifyRedirectURI = "http://localhost:8080/"

    try:
        with open("./credentials.json", "r") as creds_json:
            creds = json.load(creds_json)

            load = input("Found previously used credentials."
                         " Want to use them again? (Y/N) "
                        ).lower()

            if load != "y":
                if load == "n":
                    print("User didn't want to load from save.")
                    raise FileNotFoundError
                else:
                    print("Unrecognized Input.")
                    creds_json.close()  # The program exits immediately below.
                    sys.exit(0)
            
            key = getpass.getpass("Please enter the password used to encrypt your credentials\n")
            spotify_username = xor_crypt(creds["spotify_username"], key)
            spotify_client_id = xor_crypt(creds["spotify_client_id"], key)
            spotify_client_secret = xor_crypt(creds["spotify_client_secret"], key)

    except FileNotFoundError:
        spotify_username = input("Ok, what's your Spotify username? ")
        spotify_client_id = input("Great, now what's the ClientID you're using? ")
        spotify_client_secret = input("Beautiful, now how about the Client Secret? ")

        save = input("Awesome, now would you like to save these settings"
                     " for future sessions? (Y/n) "
                    ).lower()
        
        if save == "y":
            key = getpass.getpass("\nChoose a password to encrypt these settings.\nPassword should be at least 8 (ASCII) characters long.\n")
            if len(key) < 8:
                print("Password needs to be at least 8 characters long. Exiting.")
                sys.exit(0)
            if not is_ascii(key):
                print("Password can only contain ASCII characters. Exiting.")
                sys.exit(0)
            
            verification = getpass.getpass("Please verify your password.\n")
            if key != verification:
                print("Passwords do not match. Exiting.")
                sys.exit(0)

            save_obj = {
                "spotify_username": xor_crypt(spotify_username, key),
                "spotify_client_id": xor_crypt(spotify_client_id, key),
                "spotify_client_secret": xor_crypt(spotify_client_secret, key)
            }

            with open("./credentials.json", "w") as creds:
                creds.write(json.dumps(save_obj))
                creds.close()

                print("Saved.")

        elif save == "n":
            print("Not saving settings.")

        else:
            print("Didn't recognize input, defaulted to not saving.")

    main(spotify_username, spotifyAccessScope, spotify_client_id, spotify_client_secret, spotifyRedirectURI, PATH)
