import getopt
import random
import requests
import sys

API_BASE_URL = 'http://api.musixmatch.com/ws/1.1/'

class ApiError( Exception ):
    def __init__( self, message ):
        super().__init__( message )
        self.message = message


def api_call( api_key, api_method, **kwargs ):
    url = API_BASE_URL + api_method

    try:
        kwargs[ 'apikey' ] = api_key
        kwargs[ 'format' ] = 'json'
        response = requests.get( url, params = kwargs )
    except requests.ConnectionError:
        raise ApiError( 'Unable to connect to API host' )
    except requests.HTTPError:
        raise ApiError( 'An HTTP error has occurred' )
    except requests.URLRequired:
        raise ApiError( 'Invalid URL -> %s' % url )
    except requests.TooManyRedirects:
        raise ApiError( 'Too many redirects' )
    except requests.Timeout:
        raise ApiError( 'Timeout' )

    if 200 <= response.status_code < 300:
        try:
            json = response.json()
        except ValueError:
            raise ApiError( 'Invalid JSON response' )
    else:
        raise ApiError( 'API error -> %s (%s)' % ( url, response.reason ) )

    # Musix Match returns 200 for all API responses, even those that fail.
    # Check message.header.status_code for actual status code.
    api_status_code = json[ 'message' ][ 'header' ][ 'status_code' ]

    if not ( 200 <= api_status_code < 300 ):
        # No reason message supplied by Musix Match
        raise ApiError( 'API error -> %s (%d)' % ( url, api_status_code ) )

    return json


def get_artist_track_ids( api_key, artist, sample_size ):
    json = api_call( api_key, 'track.search',
                     q_artist = artist, page_size = sample_size )
    return [ entry[ 'track' ][ 'track_id' ] \
                for entry in json[ 'message' ][ 'body' ][ 'track_list' ] ]


def get_track_lyrics( api_key, track_id ):
    json = api_call( api_key, 'track.lyrics.get', track_id = track_id )
    return json[ 'message' ][ 'body' ][ 'lyrics' ][ 'lyrics_body' ]


def get_lyrics_corpus( api_key, artist, sample_size ):
    print( "Retrieving track ID's for '%s'" % artist )

    track_ids = get_artist_track_ids( api_key, artist, sample_size )
    corpus = []

    for track_id in track_ids:
        print( "Retrieving lyrics for track %s" % track_id )
        lyrics = get_track_lyrics( api_key, track_id )
        lyrics = lyrics.replace( '\n\n', '\n' ).split( '\n' )

        if lyrics[ -1 ] == '(1409616144139)':
            # Remove commercial licence warning
            lyrics = lyrics[ :-4 ]

        corpus.append( '\n '.join( lyrics ) )

    return corpus


def build_distribution( corpus ):
    distribution = {}

    for song in corpus:
        song = song.split( ' ' )

        if len( song ) < 3:
            continue

        prev_word1 = song[ 0 ]
        prev_word2 = song[ 1 ]

        for word in song[ 2: ]:
            key = ( prev_word1, prev_word2 )

            if key in distribution:
                distribution[ key ].append( word )
            else:
                distribution[ key ] = [ word ]

            prev_word1 = prev_word2
            prev_word2 = word

    return distribution


def generate_song( corpus, word_count ):
    distribution = build_distribution( corpus )
    word_pairs = list( distribution.keys() )
    word1 = None
    word2 = None
    song = []

    for i in range( word_count - 1 ):
        if word1 == None:
            word1, word2 = random.choice( word_pairs )

        song.append( word1 )
        key = ( word1, word2 )

        if key in distribution:
            word1, word2 = word2, random.choice( distribution[ key ] )
        else:
            # Word pair occurs at the end of a song. No word following pair.
            # Pick a new pair.
            song.append( word2 )
            word1 = None

    song.append( word2 )

    return ' '.join( song ).replace( '\n ', '\n' )


def parse_cmdline_options( args ):
    try:
        opts, _ = getopt.getopt( args,
                                 'k:a:swh',
                                 [ 'apikey=', 'artist=', 'samplesize=',
                                   'wordcount=', 'help' ] )
        result = { 'sample_size': 25, 'word_count': 50 }

        for opt, arg in opts:
            if opt == '-k' or opt == '--apikey':
                result[ 'api_key' ] = arg
            elif opt == '-a' or opt == '--artist':
                result[ 'artist' ] = arg
            elif opt == '-s' or opt == '--samplesize':
                try:
                    result[ 'sample_size' ] = int( arg )
                except ValueError:
                    pass
            elif opt == '-w' or opt == '--wordcount':
                try:
                    result[ 'word_count' ] = int( arg )
                except ValueError:
                    pass
            elif opt == '-h' or opt == '--help':
                result[ 'help' ] = True

        # Clamp sample size between 5 and 100 (Musix Match allows max of 100
        # per track query page) #laziness #sueMe
        result[ 'sample_size' ] = min( max( result[ 'sample_size' ], 5 ), 100 )

        return result
    except getopt.GetoptError:
        return {}


def print_usage_and_exit():
    print( 'Usage: %s -k <API key> -a <artist>' % sys.argv[ 0 ] )
    sys.exit()


def main():
    if len( sys.argv ) == 1:
        print_usage_and_exit()

    options = parse_cmdline_options( sys.argv[ 1: ] )
    required_options = [ 'api_key', 'artist' ]

    if 'help' in options or \
        not all( [ required in options for required in required_options ] ):
        print_usage_and_exit()

    try:
        corpus = get_lyrics_corpus( options[ 'api_key' ],
                                    options[ 'artist' ],
                                    options[ 'sample_size' ] )
    except ApiError as err:
        print( "Unable to retrieve lyrics: %s" % err, file = sys.stderr )
        sys.exit( -1 )

    song = generate_song( corpus, options[ 'word_count' ] )
    print( 'Done' )
    print()
    print( 'Song' )
    print( '====' )
    print( song )


if __name__ == '__main__':
    main()
