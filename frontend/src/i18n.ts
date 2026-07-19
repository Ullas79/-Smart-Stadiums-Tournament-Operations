import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: {
        translation: {
          "title": "Smart Stadiums Assistant",
          "subtitle": "FIFA World Cup 2026 Final · MetLife Stadium",
          "language": "Language",
          "fan": "Fan",
          "volunteer": "Volunteer",
          "organizer": "Organizer",
          "staff": "Staff",
          "loading": "Loading live state…",
          "phase": "Phase: {{phase}}",
          "send": "Send",
          "askPlaceholder": "Ask as {{role}}…",
          "weather": "72°F Partly Cloudy",
          "noIncidents": "No active incidents.",
          "activeIncidents": "Active Incidents ({{count}})",
          "crowdDensity": "Crowd Density Matrix",
          "gates": "Gates & Queues",
          "transit": "Transit Wait Times",
          "chatEmpty": "Ask the Smart Stadiums Assistant about navigation, crowds, schedule, or incidents.",
          "chatTools": "{{count}} tool call(s)",
          "you": "You",
          "assistant": "Assistant"
        }
      },
      es: {
        translation: {
          "title": "Asistente de Estadios",
          "subtitle": "Final Copa Mundial 2026 · MetLife Stadium",
          "language": "Idioma",
          "fan": "Aficionado",
          "volunteer": "Voluntario",
          "organizer": "Organizador",
          "staff": "Personal",
          "loading": "Cargando…",
          "phase": "Fase: {{phase}}",
          "send": "Enviar",
          "askPlaceholder": "Preguntar como {{role}}…",
          "weather": "22°C Algo Nublado",
          "noIncidents": "Sin incidentes.",
          "activeIncidents": "Incidentes ({{count}})",
          "crowdDensity": "Matriz de Multitudes",
          "gates": "Puertas y Filas",
          "transit": "Tiempos de Tránsito",
          "chatEmpty": "Pregúntale al Asistente sobre navegación, multitudes, horarios o incidentes.",
          "chatTools": "{{count}} llamada(s)",
          "you": "Tú",
          "assistant": "Asistente"
        }
      },
      fr: {
        translation: {
          "title": "Assistant Stades Intelligents",
          "subtitle": "Finale Coupe du Monde 2026 · MetLife Stadium",
          "language": "Langue",
          "fan": "Supporter",
          "volunteer": "Bénévole",
          "organizer": "Organisateur",
          "staff": "Personnel",
          "loading": "Chargement en direct…",
          "phase": "Phase: {{phase}}",
          "send": "Envoyer",
          "askPlaceholder": "Demander en tant que {{role}}…",
          "weather": "22°C Partiellement Nuageux",
          "noIncidents": "Aucun incident actif.",
          "activeIncidents": "Incidents Actifs ({{count}})",
          "crowdDensity": "Matrice de Densité",
          "gates": "Portes et Files d'attente",
          "transit": "Temps de Transit",
          "chatEmpty": "Posez des questions sur la navigation, les foules, les horaires ou les incidents.",
          "chatTools": "{{count}} outil(s)",
          "you": "Vous",
          "assistant": "Assistant"
        }
      }
    },
    lng: "en",
    fallbackLng: "en",
    interpolation: {
      escapeValue: false
    }
  });

export default i18n;
