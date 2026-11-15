"""Serviço de geocodificação para posicionamento estratégico e cálculo A2/AD."""

from typing import Optional, Tuple

from geopy.exc import GeopyError
from geopy.geocoders import Nominatim


class GeoLocatorService:
    """Converte endereços e CEPs de OMs em coordenadas geográficas (lat, lon)."""

    def __init__(self, user_agent: str = "siga-f4-geolocator"):
        self.geolocator = Nominatim(user_agent=user_agent, timeout=10)

    def geocodificar_endereco(self, endereco: str, cep: Optional[str] = None) -> Optional[Tuple[float, float]]:
        """Retorna (latitude, longitude) a partir do endereço/CEP ou None em caso de falha."""
        consulta = f"{endereco}, {cep}, Brasil" if cep else f"{endereco}, Brasil"
        try:
            location = self.geolocator.geocode(consulta)
            if location:
                return (round(location.latitude, 6), round(location.longitude, 6))
        except GeopyError:
            return None
        return None
