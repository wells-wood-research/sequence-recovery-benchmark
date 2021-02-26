"""Runs benchmark via command line."""

from benchmark import visualization
from benchmark import get_cath
from pathlib import Path
import click
import os


@click.group()
def cli():
    pass


@cli.command("Check_set")
@click.option(
    "--dataset",
    help="Path to .txt file with dataset list(PDB+chain, e.g., 1a2bA).",
    type=click.Path(exists=True),
    required=True,
)
@click.option(
    "--training_set",
    help="Path to .txt file with training set, format same as dataset or PISCES",
    type=click.Path(exists=True),
    required=True,
)
def check_set(dataset: Path, training_set: Path) -> None:
    """Checks training and testing sets for overlapping structures, suggests a non-overlaping set."""

    with open(training_set) as file:
        training_chains = [x.split()[0].strip("\n").upper() for x in file.readlines()]
        # check for pisces
        if len(training_chains[0]) != 5:
            training_chains = training_chains[1:]
    with open(dataset) as file:
        testing_chains = [x.split()[0].strip("\n").upper() for x in file.readlines()]

    repeated_chains = [x for x in testing_chains if x in training_chains]

    if len(repeated_chains) > 0:
        print(f"{len(repeated_chains)} chains are in both sets:")
        for chain in repeated_chains:
            print(chain)

        print("\n")
        print("New benchmarking set:")
        for chain in testing_chains:
            if chain not in repeated_chains:
                print(chain)
    else:
        print("There is no overlap between sets.")


@cli.command("Compare")
@click.option(
    "--dataset",
    help="Path to .txt file with dataset list (PDB+chain, e.g., 1a2bA).",
    type=click.Path(exists=True),
    required=True,
)
@click.option(
    "--path_to_pdb",
    help="Path to the directory with PDB files.",
    type=click.Path(exists=True),
    required=True,
)
@click.option(
    "--path_to_assemblies",
    help="Path to the directory with biological assemblies.",
    type=click.Path(exists=True),
    required=True,
)
@click.option(
    "--path_to_models",
    help="Path to the directory with .csv prediction files.",
    type=click.Path(exists=True),
    required=True,
)
@click.option(
    "--path_to_dataset_map",
    help="Path to the .txt file with prediction labels.",
    type=click.Path(exists=True),
    required=True,
)
@click.option(
    "--path_to_evoef",
    help="Path to the directory with EvoEF2 predictions. If supplied, EvoEF2 will be included in comparison.",
    type=click.Path(exists=True),
)
@click.option(
    "--include",
    help="Path to .txt file with a list of models to be included in comparison. If not provided, 8 models with the best accuracy are compared.",
    type=click.Path(exists=True),
)
@click.option(
    "--pdbs",
    help="Path to .txt file with a list of models and PDB codes for structures to be visualized. If not provided, no structures will be visualized.",
    type=click.Path(exists=True),
)
@click.option(
    "--by_chain",
    is_flag=True,
    help="Metrics will be calculated on a full chain, otherwise only CATH fragments are considered.",
)
@click.option(
    "--ignore_uncommon",
    is_flag=True,
    help="Select this option if your model ignores uncommon amino acids",
)
@click.option(
    "--torsions",
    is_flag=True,
    help="Produces predicted and true Ramachandran plots for each model.",
)
def compare_models(
    dataset: str,
    path_to_pdb: str,
    path_to_assemblies: str,
    path_to_models: str,
    path_to_dataset_map: str,
    path_to_evoef: str = False,
    include: str = False,
    pdbs: str = False,
    ignore_uncommon: bool = False,
    by_chain: bool = False,
    torsions: bool = False,
) -> None:
    by_fragment = not by_chain
    # get model labels to include in comparison
    if include:
        with open(include) as file:
            models_to_include = [x.strip("\n") for x in file.readlines()]
    # get pdbs to include in visualization
    if pdbs:
        pdb_dict = {}
        with open(pdbs) as file:
            for line in file.readlines():
                split_line = line.split()
                pdb_dict[split_line[0]] = [x.strip("\n") for x in split_line[1:]]
    df = get_cath.read_data("cath-domain-description-file.txt")
    filtered_df = get_cath.filter_with_user_list(df, dataset)
    df_with_sequence = get_cath.append_sequence(
        filtered_df, Path(path_to_assemblies), Path(path_to_pdb)
    )

    accuracy = []
    # load predictions
    list_of_models = {
        name: get_cath.load_prediction_matrix(
            df_with_sequence, path_to_dataset_map, Path(path_to_models) / name
        )
        for name in os.listdir(path_to_models)
        if name.split(".")[-1] == "csv"
    }
    for model in list_of_models:
        # make pdb visualization
        if pdbs:
            if model in pdb_dict:
                for protein in pdb_dict[model]:
                    visualization.show_accuracy(
                        df_with_sequence,
                        protein,
                        list_of_models[model],
                        Path(path_to_models) / f"{model}_{protein}.pdb",
                        Path(path_to_pdb),
                        ignore_uncommon,
                        False,
                    )

        # make model summary
        visualization.make_model_summary(
            df_with_sequence,
            list_of_models[model],
            str(Path(path_to_models) / model),
            Path(path_to_pdb),
            by_fragment=by_fragment,
            ignore_uncommon=ignore_uncommon,
            score_sequence=False,
        )
        # get overall accuracy
        accuracy.append(
            [
                get_cath.score(
                    df_with_sequence,
                    list_of_models[model],
                    ignore_uncommon=ignore_uncommon,
                    by_fragment=by_fragment,
                )[0][0],
                model,
            ]
        )
        # make Ramachandran plots
        if torsions:
            sequence, prediction, _, angle = get_cath.format_angle_sequence(
                df_with_sequence,
                list_of_models[model],
                Path(path_to_assemblies),
                ignore_uncommon=ignore_uncommon,
                by_fragment=by_fragment,
            )
            visualization.ramachandran_plot(
                sequence,
                list(get_cath.most_likely_sequence(prediction)),
                angle,
                str(Path(path_to_models) / model),
            )
    # load evoef predictions and make evoef summary
    if path_to_evoef:
        evo_ef2 = get_cath.load_prediction_sequence(df_with_sequence, path_to_evoef)
        visualization.make_model_summary(
            df_with_sequence,
            evo_ef2,
            str(Path(path_to_models) / "EvoEF2"),
            Path(path_to_pdb),
            by_fragment=by_fragment,
            ignore_uncommon=True,
            score_sequence=True,
        )
        if torsions:
            sequence, prediction, _, angle = get_cath.format_angle_sequence(
                df_with_sequence,
                evo_ef2,
                Path(path_to_assemblies),
                ignore_uncommon=True,
                by_fragment=by_fragment,
                score_sequence=True,
            )
            visualization.ramachandran_plot(
                sequence, prediction, angle, str(Path(path_to_models) / model)
            )

    accuracy = sorted(accuracy)
    # pick 7 best models and evoef
    if path_to_evoef:
        filtered_models = [list_of_models[model[1]] for model in accuracy[-7:]]
        filtered_labels = [model[1] for model in accuracy[-7:]]
        # add evoEF2 data
        filtered_models.append(evo_ef2)
        filtered_labels.append("EvoEF2")
    # pick 8 best models
    else:
        filtered_models = [list_of_models[model[1]] for model in accuracy[-8:]]
        filtered_labels = [model[1] for model in accuracy[-8:]]
    # include specified models
    if include:
        if len(models_to_include) <= 8:
            for index, model_name in enumerate(models_to_include):
                if model_name not in filtered_labels:
                    filtered_models[index] = list_of_models[model_name]
                    filtered_labels[index] = model_name
        else:
            raise ValueError(
                "Too many models are give to plot, select no more than 8 models."
            )

    visualization.compare_model_accuracy(
        df_with_sequence,
        filtered_models,
        filtered_labels,
        Path(path_to_models),
        ignore_uncommon,
        by_fragment,
    )


@cli.command("Run_EvoEF2")
@click.option(
    "--dataset",
    help="Path to .txt file with dataset list (PDB+chain, e.g., 1a2bA).",
    type=click.Path(exists=True),
    required=True,
)
@click.option(
    "--path_to_assemblies",
    help="Path to the directory with biological assemblies.",
    type=click.Path(exists=True),
    required=True,
)
@click.option(
    "--working_dir",
    help="Directory where to store results.",
    type=click.Path(),
    required=True,
)
@click.option(
    "--path_to_evoef2",
    help="Path to EvoEF2 executable.",
    type=click.Path(exists=True),
    required=True,
)
@click.option(
    "--max_processes", help="Maximum number of cores to use", type=int, default=8
)
def run_evoEF2(
    dataset: str,
    working_dir: str,
    path_to_evoef2: str,
    max_processes: int,
    path_to_assemblies: str,
) -> None:
    """Runs EvoEF2 sequence predictions on a specified set."""

    df = get_cath.read_data("cath-domain-description-file.txt")
    filtered_df = get_cath.filter_with_user_list(df, dataset)

    get_cath.multi_Evo2EF(
        filtered_df,
        1,
        max_processes=max_processes,
        working_dir=Path(working_dir),
        path_to_evoef2=Path(path_to_evoef2),
        path_to_assemblies=Path(path_to_assemblies),
    )


if __name__ == "__main__":
    cli()