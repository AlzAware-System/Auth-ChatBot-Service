from flask import Blueprint

from app.controllers.matching_game_controller import (
    upload_matching_item,
    start_matching_game,
    submit_matching_answers,
    get_my_items,
    delete_matching_item,
    get_game_history,
)

matching_game_bp = Blueprint('matching_game', __name__)


@matching_game_bp.route('/upload', methods=['POST'])
def upload_route():
    return upload_matching_item()


@matching_game_bp.route('/start', methods=['GET'])
def start_route():
    return start_matching_game()


@matching_game_bp.route('/submit', methods=['POST'])
def submit_route():
    return submit_matching_answers()


@matching_game_bp.route('/my-items', methods=['GET'])
def my_items_route():
    return get_my_items()


@matching_game_bp.route('/<string:item_id>', methods=['DELETE'])
def delete_item_route(item_id):
    return delete_matching_item(item_id)


@matching_game_bp.route('/history', methods=['GET'])
def history_route():
    return get_game_history()
