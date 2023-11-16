# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet , EventType
import requests
import sqlalchemy 
import tmdbsimple as tmdb
from rasa.shared.core.trackers import DialogueTracker
from rasa.shared.core.domain import Domain
import rasa.shared.core.domain.data 
tmdb.API_KEY = '0469589b5215ebdb5e05fc245ff4b464'
tmdb.REQUESTS_TIMEOUT = 5  
tmdb.REQUESTS_SESSION = requests.Session()

loading = requests

class ActionRecomendarContenido(Action):
    def name(self):
        return "action_recomendar_contenido"

    def run(self, dispatcher, tracker, domain):
        genero = tracker.get_slot("genre")
        tipo_contenido = tracker.get_slot("tipo_contenido")

        if not genero or not tipo_contenido:
            dispatcher.utter_response("utter_no_genero_tipo_contenido")
            return []

        tipo_a_clase = {
            "pelicula": tmdb.Movies(),
            "serie": tmdb.TV()
        }

        contenido_api = tipo_a_clase.get(tipo_contenido.lower())
        if not contenido_api:
            dispatcher.utter_response(f"utter_no_reconoce_tipo_contenido", tipo_contenido=tipo_contenido)
            return []

        genre_api = tmdb.Genres()
        genre_list = genre_api.movie_list() if tipo_contenido.lower() == "pelicula" else genre_api.tv_list()

        genre_id = next((g['id'] for g in genre_list['genres'] if g['name'].lower() == genero.lower()), None)

        if not genre_id:
            dispatcher.utter_response(f"utter_no_genero_encontrado", tipo_contenido=tipo_contenido)
            return []

        contenido = contenido_api.discover(page=1, sort='popularity.desc', with_genres=genre_id)

        if not contenido['results']:
            dispatcher.utter_response(f"utter_no_contenido_encontrado", tipo_contenido=tipo_contenido, genero=genero)
            return []

        recommendations = []
        for c in contenido['results'][:10]:
            title_key = 'title' if tipo_contenido.lower() == "pelicula" else 'name'
            nombre = c[title_key]
            puntuacion = c['vote_average']
            recommendations.append(f"Nombre: {nombre}, Puntuación: {puntuacion}")

        print("Recomendaciones:", recommendations)
        dispatcher.utter_response("utter_recomendar_contenido", recommendations=recommendations)

        return [SlotSet(f"{tipo_contenido.lower()}_encontrado", nombre)]


class ActionBuscarPorActorOActriz(Action):
    def name(self):
        return "action_buscar_por_actor_o_actriz"

    def run(self, dispatcher, tracker, domain):
        actor_o_actriz = tracker.get_slot("actor_o_actriz")

        if not actor_o_actriz:
            dispatcher.utter_message("No se especificó un actor o actriz para la búsqueda.")
            return []

        base_url = "https://api.themoviedb.org/3/person"
        response_actor = requests.get(f"{base_url}/search?query={actor_o_actriz}")

        if response_actor.status_code == 200:
            actores_resultados = response_actor.json().get("results", [])

            if actores_resultados:
                actor = actores_resultados[0]
                actor_id = actor.get("id")
                response_contenido = requests.get(f"{base_url}/{actor_id}/movie_credits")

                if response_contenido.status_code == 200:
                    contenido_relacionado = response_contenido.json().get("cast", [])

                    if contenido_relacionado:
                        message = f"Contenido relacionado con {actor_o_actriz}:\n"
                        for item in contenido_relacionado[:5]:
                            title_key = 'title' if "title" in item else 'name'
                            title = item.get(title_key)
                            message += f"- {title}\n"
                        print("Contenido relacionado:", message)
                        dispatcher.utter_message(message)
                    else:
                        dispatcher.utter_message(f"No se encontró contenido relacionado con {actor_o_actriz}.")
                else:
                    dispatcher.utter_message("No se pudo obtener información del contenido relacionado.")
            else:
                dispatcher.utter_message(f"No se encontró información para el actor o actriz {actor_o_actriz}.")
        else:
            dispatcher.utter_message("No se pudo realizar la búsqueda del actor o actriz.")

        return [SlotSet("busqueda_realizada", True)]


class ActionReproducirContenido(Action):

    def name(self) -> Text:
        return "action_reproducir_contenido"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Domain) -> None:

        # Obtén el título y el tipo de contenido de la conversación
        contenido_title = tracker.get_slot("contenido_title")
        tipo_contenido = tracker.get_slot("tipo_contenido")

        if not contenido_title or not tipo_contenido:
            dispatcher.utter_message("No se especificó un título o tipo de contenido para la reproducción.")
            return []

        # Define la URL base para la búsqueda de contenido en TMDb
        base_url = "https://api.themoviedb.org/3/search/"
        endpoint = "movie" if tipo_contenido.lower() == "pelicula" else "tv"

        # Realiza una solicitud para buscar la película o serie
        response = requests.get(f"{base_url}{endpoint}?query={contenido_title}")

        # Verifica si hay resultados y si el primer resultado es válido
        results = response.json().get("results", [])
        resultado = results[0] if results else None

        # Si el contenido existe, lo reproducimos
        if resultado:
            print("Reproduciendo contenido:", contenido_title)
            dispatcher.utter_response("utter_reproduccion", contenido_title=contenido_title)
        else:
            # Si el contenido no existe, lo comunicamos al usuario
            print(f"No se puede reproducir el contenido: {contenido_title}")
            dispatcher.utter_message("No se encuentra el {tipo_contenido}.", tipo_contenido=tipo_contenido)
        
        return []
    
class TipoContenido:
  PELICULA = "movie"
  SERIE = "tv"

class ActionAgregarAListaDeReproduccion(Action):
    def name(self) -> Text:
        return "action_agregar_a_lista_reproduccion"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Domain) -> None:

        # Obtén la información del último mensaje del usuario
        utterance = tracker.latest_message

        # Obtén la información relevante del mensaje
        tipo_contenido = utterance.get("tipo_contenido")
        contenido_id = utterance.get("contenido_id")
        lista_de_reproduccion_id = utterance.get("lista_de_reproduccion_id")

        if not tipo_contenido or not contenido_id or not lista_de_reproduccion_id:
            dispatcher.utter_message("No se especificó información suficiente para agregar a la lista de reproducción.")
            return []

        # Valida que el tipo de contenido y el ID del contenido sean válidos
        if tipo_contenido not in [TipoContenido.PELICULA, TipoContenido.SERIE]:
            dispatcher.utter_message(f"El tipo de contenido '{tipo_contenido}' no es válido.")
            return []

        if not contenido_id:
            dispatcher.utter_message("No se especificó un ID de contenido válido.")
            return []

        # Define la URL base para la adición de contenido a la lista de reproducción en TMDb
        base_url = "https://api.themoviedb.org/3/lists"

        # Agregamos el contenido a la lista de reproducción
        response = requests.post(
            f"{base_url}/{lista_de_reproduccion_id}/items",
            json={"media_id": contenido_id, "media_type": tipo_contenido}
        )

        # Si el contenido se agregó correctamente, lo notificamos al usuario
        if response.status_code == 201:
            print("Contenido agregado a la lista de reproducción") 
            dispatcher.utter_response("utter_agregar_a_lista_reproduccion")
        else:
            # Si el contenido no se agregó correctamente, lo notificamos al usuario
            dispatcher.utter_message(text="No se pudo agregar el contenido a la lista de reproducción")

        return []

# Asegúrate de tener la importación adecuada para SlotSet
from rasa_sdk.events import SlotSet

class ActionMostrarListaReproduccion(Action):
    def name(self) -> Text:
        return "action_mostrar_lista_reproduccion"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Domain) -> None:

        # Obtén el ID de la lista de reproducción del tracker
        lista_de_reproduccion_id = tracker.get_slot("lista_de_reproduccion_id")

        if not lista_de_reproduccion_id:
            dispatcher.utter_message("No se especificó una lista de reproducción.")
            return []

        # Define la URL base para obtener el contenido de la lista de reproducción en TMDb
        base_url = "https://api.themoviedb.org/3/lists"

        # Realiza una solicitud para obtener el contenido de la lista de reproducción
        response = requests.get(f"{base_url}/{lista_de_reproduccion_id}/items")

        # Si la solicitud es exitosa, muestra el contenido al usuario
        if response.status_code == 200:
            contenido_lista_re = response.json()

            # Muestra el contenido al usuario
            message = "En tu lista de reproducción:\n"
            for item in contenido_lista_re:
                title = item.get("title") or item.get("name")
                message += f"- {title}\n"
            dispatcher.utter_message(message)

        return []

class ActionEliminarDeListaReproduccion(Action):
    def name(self) -> Text:
        return "action_eliminar_de_lista_reproduccion"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Domain) -> List[EventType]:

        # Obtén la información relevante del mensaje
        tipo_contenido = tracker.get_slot("tipo_contenido")
        contenido_id = tracker.get_slot("contenido_id")
        lista_de_reproduccion_id = tracker.get_slot("lista_de_reproduccion_id")

        if not tipo_contenido or not contenido_id or not lista_de_reproduccion_id:
            dispatcher.utter_message("No se especificó información suficiente para eliminar de la lista de reproducción.")
            return []

        # Define la URL base para eliminar el contenido de la lista de reproducción en TMDb
        base_url = "https://api.themoviedb.org/3/lists"

        # Realiza una solicitud para eliminar el contenido de la lista de reproducción
        response = requests.delete(
            f"{base_url}/{lista_de_reproduccion_id}/items",
            json={"media_id": contenido_id, "media_type": tipo_contenido}
        )

        # Si la solicitud es exitosa, notifica al usuario
        if response.status_code == 200:
            dispatcher.utter_response("utter_eliminar_contenido")
        else:
            # Si la solicitud no es exitosa, notifica al usuario
            dispatcher.utter_message(text="No se pudo eliminar el contenido de la lista de reproducción.")

        return [SlotSet("eliminado", True)]

from typing import Text, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

class ActionVerPuntuacion(Action):
    def name(self) -> Text:
        return "action_ver_puntuacion"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain) -> List[SlotSet]:

        # Obtén la información relevante del tracker
        contenido_titulo = tracker.get_slot("contenido_titulo")
        tipo_contenido = tracker.get_slot("tipo_contenido")

        if not contenido_titulo or not tipo_contenido:
            dispatcher.utter_message("No se especificó información suficiente para ver la puntuación.")
            return []

        # Define la URL base para obtener la información del contenido en TMDb
        base_url = "https://api.themoviedb.org/3"

        # Realiza una solicitud para obtener la información del contenido
        response = requests.get(f"{base_url}/{tipo_contenido}/{contenido_titulo}")

        # Si la solicitud es exitosa, obtén la puntuación y notifica al usuario
        if response.status_code == 200:
            contenido_info = response.json()

            # Asegúrate de que la clave 'vote_average' exista en la respuesta
            if 'vote_average' in contenido_info:
                puntuacion = contenido_info['vote_average']
                dispatcher.utter_message(f"La puntuación de {contenido_titulo} es {puntuacion}")
            else:
                dispatcher.utter_message(f"No se encontró información de puntuación para {contenido_titulo}.")
        else:
            # Si la solicitud no es exitosa, notifica al usuario
            dispatcher.utter_message(text="No se pudo obtener la información de puntuación.")

        return [SlotSet("puntuacion_obtenida", True)]

class ActionCambiarIdioma(Action):

    def name(self) -> Text:
        return "action_cambiar_idioma"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain) -> List[SlotSet]:
        
        # Obtén el nuevo idioma de la ranura
        nuevo_idioma = tracker.get_slot("nuevo_idioma")

        if not nuevo_idioma:
            dispatcher.utter_message("No se especificó un nuevo idioma.")
            return []

        # Guarda el nuevo idioma en la ranura "language"
        return [SlotSet("languaje", nuevo_idioma), SlotSet("nuevo_idioma", None)]  # Limpia la ranura "nuevo_idioma"

        # Notifica al usuario del cambio de idioma
        dispatcher.utter_response("utter_cambiar_idioma")

class ActionSaludar(Action):
    def name(self) -> Text:
        return "action_saludar"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain) -> List[SlotSet]:
        dispatcher.utter_response("utter_saludo")
        return []

class ActionBuscarContenidoPorNombre(Action):
    def name(self) -> Text:
        return "action_buscar_contenido_por_nombre"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain) -> List[SlotSet]:
        # Obtiene el título del contenido
        contenido_titulo = tracker.get_slot("contenido_titulo")
        tipo_contenido = tracker.get_slot("tipo_contenido")

        if not contenido_titulo or not tipo_contenido:
            dispatcher.utter_message("No se especificó información suficiente para realizar la búsqueda.")
            return []

        # Define la URL base para buscar contenido por título y tipo en TMDb
        base_url = "https://api.themoviedb.org/3/search"

        # Realiza una solicitud para buscar el contenido por título y tipo
        response = requests.get(f"{base_url}/{tipo_contenido}?query={contenido_titulo}")

        # Si la solicitud es exitosa, obtén la información del contenido y notifica al usuario
        if response.status_code == 200:
            resultados = response.json().get("results", [])

            if resultados:
                # Muestra información sobre los primeros resultados encontrados
                message = f"Resultados para '{contenido_titulo}' ({tipo_contenido}):\n"
                for resultado in resultados[:5]:  # Limita a mostrar los primeros 5 resultados
                    title = resultado.get("title") if "title" in resultado else resultado.get("name")
                    message += f"- {title}\n"
            else:
                message = f"No se encontraron resultados para '{contenido_titulo}'."
            
            dispatcher.utter_message(message)
        else:
            # Si la solicitud no es exitosa, notifica al usuario
            dispatcher.utter_message(text="No se pudo realizar la búsqueda de contenido.")

        return [SlotSet("busqueda_realizada", True)]
    

class ActionDespedir(Action):
    def name(self) -> Text:
        return "action_despedir"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain) -> List[SlotSet]:
        dispatcher.utter_response("utter_despedida")
        return [SlotSet("lista_de_rep", None)]

class ActionUtterDesconocido(Action):
    def name(self) -> Text:
        return "utter_desconocido"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain) -> List[SlotSet]:
        dispatcher.utter_message("No entendí lo que quisiste decir.")
        return [SlotSet("intent_desconocida", True)]

'''
class ActionRecomendarContenido(Action):
    def name(self):
        return "action_recomendar_contenido"

    def run(self, dispatcher, tracker, domain):
        # Obtén el género y el tipo de contenido de la conversación
        genero = tracker.get_slot("genre")
        tipo_contenido = tracker.get_slot("tipo_contenido")

        if not genero or not tipo_contenido:
            dispatcher.utter_response("utter_no_genero_tipo_contenido")
            return []

        # Define el mapeo de tipo de contenido a las clases de TMDb
        tipo_a_clase = {
            "pelicula": tmdb.Movies(),
            "serie": tmdb.TV()
        }

        # Crea una instancia de la clase correspondiente a la película o serie
        contenido_api = tipo_a_clase.get(tipo_contenido.lower())
        if not contenido_api:
            dispatcher.utter_response(f"utter_no_reconoce_tipo_contenido", tipo_contenido=tipo_contenido)
            return []

        # Busca el ID del género en TMDb
        genre_api = tmdb.Genres()
        genre_list = genre_api.movie_list() if tipo_contenido.lower() == "pelicula" else genre_api.tv_list()

        genre_id = None
        for g in genre_list['genres']:
            if g['name'].lower() == genero.lower():
                genre_id = g['id']
                break

        if not genre_id:
            dispatcher.utter_response(f"utter_no_genero_encontrado", tipo_contenido=tipo_contenido)
            return []

        # Realiza una solicitud para obtener películas o series por género
        contenido = contenido_api.discover(page=1, sort='popularity.desc', with_genres=genre_id)

        if not contenido['results']:
            dispatcher.utter_response(f"utter_no_contenido_encontrado", tipo_contenido=tipo_contenido, genero=genero)
            return []

        # Formatea y presenta las recomendaciones al usuario
        recommendations = []
        for c in contenido['results'][:10]:  # Limita la cantidad de contenido recomendado
            nombre = c['title'] if tipo_contenido.lower() == "pelicula" else c['name']
            puntuacion = c['vote_average']
            recommendations.append(f"Nombre: {nombre}, Puntuación: {puntuacion}")
        
        print("Recomendaciones:", recommendations)
        dispatcher.utter_response("utter_recomendar_contenido", recommendations=recommendations)

        return [SlotSet("pelicula_encontrada", nombre)] if tipo_contenido.lower() == "pelicula" else [SlotSet("serie_encontrada", nombre)]


class ActionBuscarPorActorOActriz(Action):
    def name(self):
        return "action_buscar_por_actor_o_actriz"

    def run(self, dispatcher, tracker, domain):
        # Obtiene el nombre del actor o actriz
        actor_o_actriz = tracker.get_slot("actor_o_actriz")

        if not actor_o_actriz:
            dispatcher.utter_message("No se especificó un actor o actriz para la búsqueda.")
            return []

        # Define la URL base para buscar contenido por actor o actriz en TMDb
        base_url = "https://api.themoviedb.org/3/person"

        # Realiza una solicitud para buscar el actor o actriz por nombre
        response_actor = requests.get(f"{base_url}/search?query={actor_o_actriz}")

        if response_actor.status_code == 200:
            actores_resultados = response_actor.json().get("results", [])

            if actores_resultados:
                # Toma el primer actor o actriz encontrado
                actor = actores_resultados[0]

                # Obtiene el ID del actor o actriz
                actor_id = actor.get("id")

                # Realiza una segunda solicitud para obtener el contenido relacionado al actor o actriz
                response_contenido = requests.get(f"{base_url}/{actor_id}/movie_credits")

                if response_contenido.status_code == 200:
                    contenido_relacionado = response_contenido.json().get("cast", [])

                    if contenido_relacionado:
                        # Muestra información sobre el contenido relacionado
                        message = f"Contenido relacionado con {actor_o_actriz}:\n"
                        for item in contenido_relacionado[:5]:  # Limita a mostrar los primeros 5 resultados
                            title = item.get("title") if "title" in item else item.get("name")
                            message += f"- {title}\n"
                        print("Contenido relacionado:", message)
                        dispatcher.utter_message(message)
                    else:
                        dispatcher.utter_message(f"No se encontró contenido relacionado con {actor_o_actriz}.")
                else:
                    dispatcher.utter_message("No se pudo obtener información del contenido relacionado.")
            else:
                dispatcher.utter_message(f"No se encontró información para el actor o actriz {actor_o_actriz}.")
        else:
            dispatcher.utter_message("No se pudo realizar la búsqueda del actor o actriz.")

        return [SlotSet("busqueda_realizada", True)]


class ActionReproducirContenido(Action):

    def name(self) -> Text:
        return "action_reproducir_contenido"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Domain) -> None:

        # Obtén el título y el tipo de contenido de la conversación
        contenido_title = tracker.get_slot("contenido_title")
        tipo_contenido = tracker.get_slot("tipo_contenido")

        if not contenido_title or not tipo_contenido:
            dispatcher.utter_message("No se especificó un título o tipo de contenido para la reproducción.")
            return []

        # Define la URL base para la búsqueda de contenido en TMDb
        base_url = "https://api.themoviedb.org/3/search/"
        endpoint = "movie" if tipo_contenido.lower() == "pelicula" else "tv"

        # Realiza una solicitud para buscar la película o serie
        response = requests.get(f"{base_url}{endpoint}?query={contenido_title}")
        resultado = response.json()["results"][0]

        # Si el contenido existe, lo reproducimos
        if resultado is not None:
            print("Reproduciendo contenido:", contenido_title)
            dispatcher.utter_response("utter_reproduccion", contenido_title=contenido_title)
        else:
            # Si el contenido no existe, lo comunicamos al usuario
            print(f"No se puede reproducir el contenido: {contenido_title}")
            dispatcher.utter_response("utter_no_se_puede_reproducir", tipo_contenido=tipo_contenido)
        
        return []
    
class TipoContenido:
  PELICULA = "movie"
  SERIE = "tv"

class ActionAgregarAListaDeReproduccion(Action):
    def name(self) -> Text:
        return "action_agregar_a_lista_reproduccion"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Domain) -> None:

        # Obtén la información del último mensaje del usuario
        utterance = tracker.latest_message

        # Obtén la información relevante del mensaje
        tipo_contenido = utterance.get("tipo_contenido")
        contenido_id = utterance.get("contenido_id")
        lista_de_reproduccion_id = utterance.get("lista_de_reproduccion_id")

        if not tipo_contenido or not contenido_id or not lista_de_reproduccion_id:
            dispatcher.utter_message("No se especificó información suficiente para agregar a la lista de reproducción.")
            return []

        # Valida que el tipo de contenido y el ID del contenido sean válidos
        if not TipoContenido.get(tipo_contenido):
            dispatcher.utter_message(f"El tipo de contenido '{tipo_contenido}' no es válido.")
            return []

        if not contenido_id:
            dispatcher.utter_message("No se especificó un ID de contenido válido.")
            return []

        # Define la URL base para la adición de contenido a la lista de reproducción en TMDb
        base_url = "https://api.themoviedb.org/3/lists"

        # Agregamos el contenido a la lista de reproducción
        response = requests.post(
            f"{base_url}/{lista_de_reproduccion_id}/items",
            json={"media_id": contenido_id, "media_type": tipo_contenido}
        )

        # Si el contenido se agregó correctamente, lo notificamos al usuario
        if response.status_code == 201:
            print("Contenido agregado a la lista de reproducción") 
            dispatcher.utter_response("utter_agregar_a_lista_reproduccion")
        else:
            # Si el contenido no se agregó correctamente, lo notificamos al usuario
            dispatcher.utter_message(text="No se pudo agregar el contenido a la lista de reproducción")

        return []


class ActionMostrarListaReproduccion(Action):
    def name(self) -> Text:
        return "action_mostrar_lista_reproduccion"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Domain) -> None:

        # Obtén el ID de la lista de reproducción del tracker
        lista_de_reproduccion_id = tracker.get_slot("lista_de_reproduccion_id")

        if not lista_de_reproduccion_id:
            dispatcher.utter_message("No se especificó una lista de reproducción.")
            return []

        # Valida que el ID de la lista de reproducción sea válido
        if not lista_de_reproduccion_id:
            dispatcher.utter_message("No se especificó un ID de lista de reproducción válido.")
            return []

        # Define la URL base para obtener el contenido de la lista de reproducción en TMDb
        base_url = "https://api.themoviedb.org/3/lists"

        # Realiza una solicitud para obtener el contenido de la lista de reproducción
        response = requests.get(f"{base_url}/{lista_de_reproduccion_id}/items")

        # Si la solicitud es exitosa, muestra el contenido al usuario
        if response.status_code == 200:
            contenido_lista_re = response.json()

            # Muestra el contenido al usuario
            message = "En tu lista de reproducción:\n"
            for item in contenido_lista_re:
                title = item.get("title") if "title" in item else item.get("name")
                message += f"- {title}\n"
            dispatcher.utter_message(message)

        return []

   

class ActionEliminarDeListaReproduccion(Action):
    def name(self) -> Text:
        return "action_eliminar_de_lista_reproduccion"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Domain) -> List[EventType]:

        # Obtén la información del último mensaje del usuario
        utterance = tracker.latest_message

        # Obtén la información relevante del mensaje
        tipo_contenido = utterance.get("tipo_contenido")
        contenido_id = utterance.get("contenido_id")
        lista_de_reproduccion_id = utterance.get("lista_de_reproduccion_id")

        if not tipo_contenido or not contenido_id or not lista_de_reproduccion_id:
            dispatcher.utter_message("No se especificó información suficiente para eliminar de la lista de reproducción.")
            return []

        # Define la URL base para eliminar el contenido de la lista de reproducción en TMDb
        base_url = "https://api.themoviedb.org/3/lists"

        # Realiza una solicitud para eliminar el contenido de la lista de reproducción
        response = requests.delete(
            f"{base_url}/{lista_de_reproduccion_id}/items",
            json={"media_id": contenido_id, "media_type": tipo_contenido}
        )

        # Si la solicitud es exitosa, notifica al usuario
        if response.status_code == 200:
            dispatcher.utter_response("utter_eliminar_contenido")
        else:
            # Si la solicitud no es exitosa, notifica al usuario
            dispatcher.utter_message(text="No se pudo eliminar el contenido de la lista de reproducción.")

        return [SlotSet("eliminado", True)]

class ActionVerPuntuacion(Action):
    def name(self) -> Text:
        return "action_ver_puntuacion"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: DialogueTracker,
            domain: Domain) -> None:

        # Obtén la información del último mensaje del usuario
        utterance = tracker.latest_message

        # Obtén la información relevante del mensaje
        contenido_titulo = utterance.get("contenido_titulo")
        tipo_contenido = utterance.get("tipo_contenido")

        if not contenido_titulo or not tipo_contenido:
            dispatcher.utter_message("No se especificó información suficiente para ver la puntuación.")
            return []

        # Define la URL base para obtener la información del contenido en TMDb
        base_url = "https://api.themoviedb.org/3"

        # Realiza una solicitud para obtener la información del contenido
        response = requests.get(f"{base_url}/{tipo_contenido}/{contenido_titulo}")

        # Si la solicitud es exitosa, obtén la puntuación y notifica al usuario
        if response.status_code == 200:
            contenido_info = response.json()

            # Asegúrate de que la clave 'vote_average' exista en la respuesta
            if 'vote_average' in contenido_info:
                puntuacion = contenido_info['vote_average']
                dispatcher.utter_message(f"La puntuación de {contenido_titulo} es {puntuacion}")
            else:
                dispatcher.utter_message(f"No se encontró información de puntuación para {contenido_titulo}.")
        else:
            # Si la solicitud no es exitosa, notifica al usuario
            dispatcher.utter_message(text="No se pudo obtener la información de puntuación.")

        return [SlotSet("puntuacion_obtenida", True)]


class ActionSaludar(Action):
    def name(self):
        return "action_saludar"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        dispatcher.utter_response("utter_saludo")
        return []

class ActionBuscarContenidoPorNombre(Action):
    def name(self):
        return "action_buscar_contenido_por_nombre"

    def run(self, dispatcher, tracker, domain):
        # Obtiene el título del contenido
        contenido_titulo = tracker.get_slot("contenido_titulo")
        tipo_contenido = tracker.get_slot("tipo_contenido")

        if not contenido_titulo or not tipo_contenido:
            dispatcher.utter_message("No se especificó información suficiente para realizar la búsqueda.")
            return []

        # Define la URL base para buscar contenido por título y tipo en TMDb
        base_url = "https://api.themoviedb.org/3/search"

        # Realiza una solicitud para buscar el contenido por título y tipo
        response = requests.get(f"{base_url}/{tipo_contenido}?query={contenido_titulo}")

        # Si la solicitud es exitosa, obtén la información del contenido y notifica al usuario
        if response.status_code == 200:
            resultados = response.json().get("results", [])

            if resultados:
                # Muestra información sobre los primeros resultados encontrados
                message = f"Resultados para '{contenido_titulo}' ({tipo_contenido}):\n"
                for resultado in resultados[:5]:  # Limita a mostrar los primeros 5 resultados
                    title = resultado.get("title") if "title" in resultado else resultado.get("name")
                    message += f"- {title}\n"
            else:
                message = f"No se encontraron resultados para '{contenido_titulo}'."
            
            dispatcher.utter_message(message)
        else:
            # Si la solicitud no es exitosa, notifica al usuario
            dispatcher.utter_message(text="No se pudo realizar la búsqueda de contenido.")

        return [SlotSet("busqueda_realizada", True)]
    
class ActionDespedir(Action):
    def name(self):
        return "action_despedir"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        dispatcher.utter_response("utter_despedida")
        return [SlotSet("lista_de_rep", None)]


class ActionUtterDesconocido(Action):
    def name(self):
        return "utter_desconocido"

    def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message("No entendí lo que quisiste decir.")
        return [SlotSet("intent_desconocida", True)]  
'''